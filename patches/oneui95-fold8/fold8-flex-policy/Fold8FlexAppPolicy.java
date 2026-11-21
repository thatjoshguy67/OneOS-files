package com.android.server.wm;

import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.provider.Settings;
import android.util.Base64;
import android.util.Log;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.json.JSONException;
import org.json.JSONObject;

/** Implements the app options used by Samsung Settings and Shell's Flex Panel. */
final class Fold8FlexAppPolicy {
    private static final String TAG = "Fold8FlexAppPolicy";
    // Share the existing Fold8 module's guest-side selections if present.
    private static final String KEY_PREFIX = "fold8_flex_restore_apps_u";
    private static final String OPT_OUT = "com.samsung.android.unsupports_flexpanel";
    private static final int SELECTED = 1;
    private static final int RESIZABLE = 8;
    private static final int NATIVE_LAYOUT = 16;
    private static final int HOME = 38;
    private static final int UNSUPPORTED = 70;
    private static Set<String> nativeApps;

    static int getFlags(Context userContext, int userId, String packageName, boolean forceResizable) {
        if (userId < 0 || packageName == null || packageName.isEmpty()) {
            return UNSUPPORTED;
        }
        PackageManager pm = userContext.getPackageManager();
        Intent home = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME).setPackage(packageName);
        for (ResolveInfo result : pm.queryIntentActivities(home, 0)) {
            if (result.activityInfo != null && packageName.equals(result.activityInfo.packageName)) {
                return HOME;
            }
        }
        ApplicationInfo app;
        try {
            app = pm.getApplicationInfo(packageName, PackageManager.GET_META_DATA);
        } catch (PackageManager.NameNotFoundException e) {
            return UNSUPPORTED;
        }
        if (app.metaData != null && app.metaData.getBoolean(OPT_OUT)) {
            return UNSUPPORTED;
        }

        Intent launcher = new Intent(Intent.ACTION_MAIN)
                .addCategory(Intent.CATEGORY_LAUNCHER)
                .setPackage(packageName);
        List<ResolveInfo> activities = pm.queryIntentActivities(launcher, 0);
        if (activities.isEmpty() || (!forceResizable && !supportsSplit(activities))) {
            return UNSUPPORTED;
        }

        int flags = RESIZABLE;
        if (hasNativeLayout(userContext, packageName)) {
            flags |= NATIVE_LAYOUT;
        }
        try {
            if (readChoices(userContext.getContentResolver(), userId).optBoolean(packageName)) {
                flags |= SELECTED;
            }
        } catch (JSONException e) {
            Log.w(TAG, "Could not read Flex Panel app choices for user " + userId, e);
        }
        return flags;
    }

    private static boolean supportsSplit(List<ResolveInfo> activities) {
        for (ResolveInfo result : activities) {
            ActivityInfo activity = result.activityInfo;
            if (activity != null && (activity.supportsPictureInPicture()
                    || (ActivityInfo.isResizeableMode(activity.resizeMode)
                    && !ActivityInfo.isPreserveOrientationMode(activity.resizeMode)))) {
                return true;
            }
        }
        return false;
    }

    private static synchronized boolean hasNativeLayout(Context context, String packageName) {
        if (nativeApps == null) {
            Set<String> packages = new HashSet<>();
            int id = context.getResources().getIdentifier("scpm_foldable_package_policy", "raw", "android");
            if (id != 0) {
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                        context.getResources().openRawResource(id), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        String[] fields = line.split(",", -1);
                        if (fields.length >= 3 && "flexModeApp".equals(fields[2])
                                && (fields.length < 4 || fields[3].isEmpty() || "fold".equals(fields[3]))) {
                            packages.add(new String(Base64.decode(fields[1], Base64.DEFAULT),
                                    StandardCharsets.UTF_8));
                        }
                    }
                } catch (IOException | IllegalArgumentException e) {
                    Log.w(TAG, "Could not read Samsung's native foldable app policy", e);
                }
            }
            nativeApps = packages;
        }
        return nativeApps.contains(packageName);
    }

    static synchronized void setSelected(Context userContext, int userId, String packageName,
            boolean selected, boolean forceResizable) {
        if (userId < 0 || packageName == null || packageName.isEmpty()) {
            throw new IllegalArgumentException("A Flex Panel selection needs a user and package");
        }
        if (selected && (getFlags(userContext, userId, packageName, forceResizable) & RESIZABLE) == 0) {
            return;
        }

        ContentResolver resolver = userContext.getContentResolver();
        try {
            JSONObject choices = readChoices(resolver, userId);
            if (choices.optBoolean(packageName) == selected) {
                return;
            }
            if (selected) {
                choices.put(packageName, true);
            } else {
                choices.remove(packageName);
            }
            if (!Settings.Global.putString(resolver, KEY_PREFIX + userId, choices.toString())) {
                throw new IllegalStateException("Could not save Flex Panel app choices");
            }
        } catch (JSONException e) {
            throw new IllegalStateException("Could not update Flex Panel app choices", e);
        }
    }

    private static JSONObject readChoices(ContentResolver resolver, int userId) throws JSONException {
        String value = Settings.Global.getString(resolver, KEY_PREFIX + userId);
        return value == null || value.isEmpty() ? new JSONObject() : new JSONObject(value);
    }

    private Fold8FlexAppPolicy() {}
}

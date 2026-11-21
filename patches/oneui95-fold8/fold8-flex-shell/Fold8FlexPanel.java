package com.android.wm.shell.flexpanel;

import android.app.KeyguardManager;
import android.app.PendingIntent;
import android.app.ActivityManager.RunningTaskInfo;
import android.content.BroadcastReceiver;
import android.content.ComponentCallbacks;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.res.Configuration;
import android.database.ContentObserver;
import android.hardware.devicestate.DeviceState;
import android.hardware.devicestate.DeviceStateManager;
import android.net.Uri;
import android.os.Handler;
import android.os.PowerManager;
import android.os.SystemClock;
import android.provider.Settings;
import android.util.Log;

import com.android.wm.shell.ShellTaskOrganizer;
import com.android.wm.shell.common.DisplayImeController;
import com.android.wm.shell.controlpanel.activity.FlexPanelActivity;
import com.android.wm.shell.splitscreen.SplitScreenController;
import com.samsung.android.view.SemWindowManager;

import java.util.concurrent.Executor;

/** Drives Samsung's existing panel and navigation shortcut from the Fold8 posture. */
public final class Fold8FlexPanel {
    private static final String TAG = "Fold8FlexPanel";
    private static final String PANEL = "com.android.wm.shell.controlpanel.activity.FlexPanelActivity";
    private static final String MASTER = "flex_mode_panel_enabled";
    private static final String APP_CHOICES = "fold8_flex_restore_apps_u";
    private static final String TOGGLE = "com.android.systemui.oneos.TOGGLE_FLEX_PANEL";
    private static final String SHADE_OPEN = "com.samsung.systemui.statusbar.EXPANDED";
    private static final String SHADE_CLOSED = "com.samsung.systemui.statusbar.COLLAPSED";
    private static final int MAIN_DISPLAY = 0;
    private static final int HALF_OPEN_STATE = 2;
    private static final int HALF_OPEN_PROPERTY = 2;
    private static final int COVER_PANEL = 5;
    private static final int NO_TASK = -1;
    private static final int APP_SELECTED = 1;
    private static final int APP_RESIZABLE = 8;
    private static final int APP_EXCLUDED = 4 | 32 | 64;
    private static final int OPEN_ICON = 0x7e08084e;
    private static final int CLOSE_ICON = 0x7e08084c;
    private static final long AUTO_DELAY_MILLIS = 900;
    private static final long LAUNCH_TIMEOUT_MILLIS = 7000;
    private static volatile Fold8FlexPanel active;

    private final Context context;
    private final Executor executor;
    private final Handler timer;
    private final FlexPanelStartController shortcut;
    private final SplitScreenController split;
    private final KeyguardManager keyguard;
    private final PowerManager power;
    private final Runnable autoOpen = () -> executorExecute(this::runAutoOpen);
    private final Runnable launchTimeout = () -> executorExecute(this::onLaunchTimeout);

    private boolean halfOpen;
    private boolean imeVisible;
    private boolean shadeOpen;
    private boolean panelWasVisible;
    private int buttonIcon;
    private int scheduledTaskId = NO_TASK;
    private long autoDeadline;
    private int attemptedTaskId = NO_TASK;
    private int launchedTaskId = NO_TASK;
    private int dismissedTaskId = NO_TASK;
    private RunningTaskInfo focused;

    public static void start(Context context, Executor executor, ShellTaskOrganizer organizer,
            DisplayImeController ime, FlexPanelStartController shortcut, SplitScreenController split) {
        if (active != null || shortcut == null
                || !"com.android.systemui".equals(context.getPackageName())) {
            return;
        }
        DeviceStateManager deviceState = context.getSystemService(DeviceStateManager.class);
        if (deviceState == null) {
            return;
        }

        Fold8FlexPanel panel = new Fold8FlexPanel(context, executor, shortcut, split);
        try {
            deviceState.registerCallback(executor, new DeviceStateManager.DeviceStateCallback() {
                @Override public void onDeviceStateChanged(DeviceState state) {
                    panel.onPosture(state);
                }
            });
        } catch (RuntimeException e) {
            Log.e(TAG, "Could not register the Fold8 posture callback", e);
            return;
        }
        active = panel;
        try {
            panel.register(organizer, ime);
        } catch (RuntimeException e) {
            Log.e(TAG, "Could not register the Fold8 Flex Panel listeners", e);
        }
    }

    private Fold8FlexPanel(Context context, Executor executor, FlexPanelStartController shortcut,
            SplitScreenController split) {
        this.context = context;
        this.executor = executor;
        this.timer = new Handler(context.getMainLooper());
        this.shortcut = shortcut;
        this.split = split;
        this.keyguard = context.getSystemService(KeyguardManager.class);
        this.power = context.getSystemService(PowerManager.class);
    }

    private void register(ShellTaskOrganizer organizer, DisplayImeController ime) {
        // Leave the organizer's lock before querying the split state or window service.
        organizer.addFocusListener(task -> timer.post(() -> executorExecute(() -> {
            focused = task;
            evaluate();
        })));
        ime.addPositionProcessor(new DisplayImeController.ImePositionProcessor() {
            @Override public void onImeVisibilityChanged(int displayId, boolean showing) {
                if (displayId == MAIN_DISPLAY) {
                    executorExecute(() -> {
                        imeVisible = showing;
                        evaluate();
                    });
                }
            }
        });
        IntentFilter actions = new IntentFilter(TOGGLE);
        actions.addAction(SHADE_OPEN);
        actions.addAction(SHADE_CLOSED);
        actions.addAction(Intent.ACTION_SCREEN_ON);
        actions.addAction(Intent.ACTION_SCREEN_OFF);
        actions.addAction(Intent.ACTION_USER_PRESENT);
        context.registerReceiver(new BroadcastReceiver() {
            @Override public void onReceive(Context ignored, Intent intent) {
                String action = intent.getAction();
                executorExecute(() -> onBroadcast(action));
            }
        }, actions, Context.RECEIVER_NOT_EXPORTED);
        context.getContentResolver().registerContentObserver(Settings.Global.CONTENT_URI, true,
                new ContentObserver(timer) {
                    @Override public void onChange(boolean selfChange, Uri uri) {
                        String field = uri == null ? null : uri.getLastPathSegment();
                        if (field == null || MASTER.equals(field) || field.startsWith(APP_CHOICES)) {
                            executorExecute(Fold8FlexPanel.this::evaluate);
                        }
                    }
                });
        context.registerComponentCallbacks(new ComponentCallbacks() {
            @Override public void onConfigurationChanged(Configuration configuration) {
                executorExecute(Fold8FlexPanel.this::evaluate);
            }
            @Override public void onLowMemory() {}
        });
    }

    private void executorExecute(Runnable work) {
        executor.execute(work);
    }

    public static void onPanelChanged() {
        Fold8FlexPanel panel = active;
        if (panel != null) {
            panel.executorExecute(panel::evaluate);
        }
    }

    private void onPosture(DeviceState state) {
        halfOpen = state.getIdentifier() == HALF_OPEN_STATE
                && state.getConfiguration().getPhysicalProperties().contains(HALF_OPEN_PROPERTY);
        if (!halfOpen) {
            attemptedTaskId = NO_TASK;
            dismissedTaskId = NO_TASK;
        }
        evaluate();
    }

    private void onBroadcast(String action) {
        if (TOGGLE.equals(action)) {
            FlexPanelActivity panel = visiblePanel();
            if (panel != null) {
                dismissedTaskId = launchedTaskId;
                closePanel(panel);
            } else {
                startPanel(false);
            }
        } else if (SHADE_OPEN.equals(action) || SHADE_CLOSED.equals(action)) {
            shadeOpen = SHADE_OPEN.equals(action);
        }
        evaluate();
    }

    private static FlexPanelActivity visiblePanel() {
        FlexPanelActivity panel = FlexPanelActivity.sFlexPanelActivity;
        return panel != null && !panel.isFinishing() && !panel.isDestroyed() ? panel : null;
    }

    private static void closePanel(FlexPanelActivity panel) {
        panel.runOnUiThread(() -> {
            if (!panel.isFinishing() && !panel.isDestroyed()) {
                panel.finish();
            }
        });
    }

    private boolean featureEnabled() {
        return Settings.Global.getInt(context.getContentResolver(), MASTER, 1) == 1;
    }

    private boolean onInnerDisplay() {
        Configuration config = context.getResources().getConfiguration();
        return config.semDisplayDeviceType != COVER_PANEL && config.smallestScreenWidthDp >= 500;
    }

    private boolean canInteract() {
        return halfOpen && onInnerDisplay() && featureEnabled() && power.isInteractive()
                && !keyguard.isKeyguardLocked() && !imeVisible && !shadeOpen
                && !shortcut.mIsInFixedRotation;
    }

    private RunningTaskInfo candidate() {
        if (split.isSplitScreenVisible() || focused == null || focused.displayId != MAIN_DISPLAY
                || focused.topActivity == null || focused.getWindowingMode() != 1
                || focused.getActivityType() != 1 || !focused.originallySupportedMultiWindow) {
            return null;
        }
        return focused;
    }

    private static int appFlags(RunningTaskInfo task) {
        try {
            return SemWindowManager.getInstance().getSupportsFlexPanel(
                    task.userId, task.topActivity.getPackageName());
        } catch (SecurityException e) {
            Log.e(TAG, "Cannot read Flex Panel app support", e);
            return 0;
        }
    }

    private static boolean eligible(int flags) {
        return (flags & APP_RESIZABLE) != 0 && (flags & APP_EXCLUDED) == 0;
    }

    private void evaluate() {
        FlexPanelActivity panel = visiblePanel();
        if (panel != null) {
            panelWasVisible = true;
            timer.removeCallbacks(launchTimeout);
            cancelAuto();
            if (!halfOpen || !onInnerDisplay() || !featureEnabled()) {
                showButton(0);
                closePanel(panel);
            } else {
                showButton(canInteract() ? CLOSE_ICON : 0);
            }
            return;
        }
        if (panelWasVisible) {
            if (halfOpen && launchedTaskId != NO_TASK) {
                dismissedTaskId = launchedTaskId;
            }
            panelWasVisible = false;
            launchedTaskId = NO_TASK;
        }
        if (!canInteract() || launchedTaskId != NO_TASK) {
            cancelAuto();
            showButton(0);
            return;
        }

        RunningTaskInfo task = candidate();
        int flags = task == null ? 0 : appFlags(task);
        if (task == null || !eligible(flags)) {
            cancelAuto();
            showButton(0);
            return;
        }
        boolean shouldAutoOpen = (flags & APP_SELECTED) != 0 && task.taskId != dismissedTaskId
                && task.taskId != attemptedTaskId;
        if (shouldAutoOpen) {
            showButton(0);
            if (scheduledTaskId != task.taskId) {
                cancelAuto();
                scheduledTaskId = task.taskId;
                autoDeadline = SystemClock.uptimeMillis() + AUTO_DELAY_MILLIS;
                timer.postAtTime(autoOpen, autoDeadline);
            }
        } else {
            cancelAuto();
            showButton(OPEN_ICON);
        }
    }

    private void cancelAuto() {
        timer.removeCallbacks(autoOpen);
        scheduledTaskId = NO_TASK;
    }

    private void runAutoOpen() {
        RunningTaskInfo task = candidate();
        if (SystemClock.uptimeMillis() < autoDeadline) {
            return;
        }
        if (task == null || task.taskId != scheduledTaskId) {
            cancelAuto();
            evaluate();
            return;
        }
        cancelAuto();
        startPanel(true);
        evaluate();
    }

    private void startPanel(boolean automatic) {
        if (!canInteract() || launchedTaskId != NO_TASK || visiblePanel() != null) {
            return;
        }
        RunningTaskInfo task = candidate();
        if (task == null) {
            return;
        }
        int flags = appFlags(task);
        if (!eligible(flags) || (automatic && ((flags & APP_SELECTED) == 0
                || task.taskId == dismissedTaskId || task.taskId == attemptedTaskId))) {
            return;
        }

        attemptedTaskId = task.taskId;
        launchedTaskId = task.taskId;
        cancelAuto();
        showButton(0);
        String action = automatic ? "android.intent.action.AUTORUN_FLEX_PANEL"
                : "android.intent.action.EXPAND_FLEX_PANEL";
        Intent launch = new Intent(action)
                .setComponent(new ComponentName("com.android.systemui", PANEL))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            // Pass the actual companion task. The one-intent Shell path can
            // fall back to launching the panel fullscreen if the task changes.
            split.startTaskAndIntent(task.taskId, launch, 1, 1);
            timer.postDelayed(launchTimeout, LAUNCH_TIMEOUT_MILLIS);
        } catch (RuntimeException e) {
            launchedTaskId = NO_TASK;
            Log.e(TAG, "Could not open the Fold8 Flex Panel", e);
        }
    }

    private void onLaunchTimeout() {
        if (visiblePanel() == null) {
            launchedTaskId = NO_TASK;
            evaluate();
        }
    }

    private void showButton(int icon) {
        if (icon == buttonIcon) {
            return;
        }
        if (icon == 0) {
            shortcut.clearButton();
        } else {
            Intent action = new Intent(TOGGLE).setPackage(context.getPackageName());
            PendingIntent toggle = PendingIntent.getBroadcast(context, 0, action, PendingIntent.FLAG_IMMUTABLE);
            shortcut.setNavigationBarButton(icon, toggle);
        }
        buttonIcon = icon;
    }
}

package com.android.wm.shell.flexpanel;

import android.content.Context;
import android.content.SharedPreferences;
import android.content.res.Configuration;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.drawable.GradientDrawable;
import android.hardware.display.DisplayManager;
import android.util.Log;
import android.view.Display;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
import android.view.WindowManager;
import android.widget.ImageButton;

final class Fold8FlexPanelHint implements View.OnTouchListener {
    private static final String TAG = "Fold8FlexPanel";
    private static final int OVERLAY = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY;
    private final Context context;
    private final SharedPreferences location;
    private final Runnable onClick;

    private WindowManager windows;
    private WindowManager.LayoutParams params;
    private ImageButton button;
    private float downX;
    private float downY;
    private int startX;
    private int startY;
    private boolean dragging;

    Fold8FlexPanelHint(Context context, Runnable onClick) {
        this.context = context;
        this.onClick = onClick;
        this.location = context.getSharedPreferences("oneos_fold8_flex_hint", Context.MODE_PRIVATE);
    }

    boolean show(int drawable, int description) {
        try {
            if (button == null) {
                if (!createWindow()) {
                    return false;
                }
                setIcon(drawable, description);
                windows.addView(button, params);
            } else {
                setIcon(drawable, description);
                constrain();
                windows.updateViewLayout(button, params);
            }
            return true;
        } catch (RuntimeException e) {
            Log.w(TAG, "Could not show the floating Flex Panel shortcut", e);
            hide();
            return false;
        }
    }

    private boolean createWindow() {
        DisplayManager displays = context.getSystemService(DisplayManager.class);
        Display display = displays.getDisplay(Display.DEFAULT_DISPLAY);
        if (display == null) {
            return false;
        }
        Context window = context.createWindowContext(display, OVERLAY, null);
        windows = window.getSystemService(WindowManager.class);
        int diameter = dp(48);
        params = new WindowManager.LayoutParams(diameter, diameter, OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL, PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.TOP | Gravity.LEFT;
        params.setTitle("Fold8 Flex Panel shortcut");
        Rect bounds = windows.getCurrentWindowMetrics().getBounds();
        params.x = location.getInt("x", dp(13));
        params.y = location.getInt("y", bounds.height() - dp(67) - params.height);
        constrain();
        button = new ImageButton(window);
        int padding = dp(10);
        button.setPadding(padding, padding, padding, padding);
        button.setElevation(dp(4));
        button.setOnClickListener(v -> onClick.run());
        button.setOnTouchListener(this);
        return true;
    }

    private void setIcon(int drawable, int description) {
        boolean dark = (context.getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
        GradientDrawable background = new GradientDrawable();
        background.setShape(GradientDrawable.OVAL);
        background.setColor(dark ? 0xee323232 : 0xeefafafa);
        button.setBackground(background);
        button.setColorFilter(dark ? 0xfffafafa : 0xff303030);
        button.setImageResource(drawable);
        button.setContentDescription(context.getString(description));
    }

    void hide() {
        if (button != null && button.isAttachedToWindow()) {
            windows.removeViewImmediate(button);
        }
        button = null;
        windows = null;
        params = null;
    }

    private int dp(int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    private void constrain() {
        Rect bounds = windows.getCurrentWindowMetrics().getBounds();
        int xMin = dp(13);
        int xMax = bounds.width() - params.width - xMin;
        int yMin = bounds.height() / 2 + dp(13);
        int yMax = bounds.height() - params.height - dp(67);
        params.x = Math.max(xMin, Math.min(params.x, xMax));
        params.y = Math.max(yMin, Math.min(params.y, yMax));
    }

    @Override
    public boolean onTouch(View view, MotionEvent event) {
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downX = event.getRawX();
                downY = event.getRawY();
                startX = params.x;
                startY = params.y;
                dragging = false;
                return true;
            case MotionEvent.ACTION_MOVE:
                float dx = event.getRawX() - downX;
                float dy = event.getRawY() - downY;
                if (Math.hypot(dx, dy) > ViewConfiguration.get(context).getScaledTouchSlop()) {
                    dragging = true;
                }
                if (dragging) {
                    params.x = startX + Math.round(dx);
                    params.y = startY + Math.round(dy);
                    constrain();
                    windows.updateViewLayout(button, params);
                }
                return true;
            case MotionEvent.ACTION_UP:
                if (dragging) {
                    location.edit().putInt("x", params.x).putInt("y", params.y).apply();
                } else {
                    view.performClick();
                }
                return true;
            case MotionEvent.ACTION_CANCEL:
                return true;
            default:
                return false;
        }
    }
}

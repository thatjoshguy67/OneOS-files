// Compile-time declarations for S948BXXU6ZZKN. Excluded from the patch DEX.
package com.android.wm.shell;
import android.app.ActivityManager.RunningTaskInfo;
public class ShellTaskOrganizer {
    public interface FocusListener {
        void onFocusTaskChanged(RunningTaskInfo task);
    }
    public native void addFocusListener(FocusListener listener);
}

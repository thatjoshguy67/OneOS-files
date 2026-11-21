// Compile-time declarations for S948BXXU6ZZKN. Excluded from the patch DEX.
package com.android.wm.shell.splitscreen;
import android.content.Intent;
public class SplitScreenController {
    public native boolean isSplitScreenVisible();
    public native void startTaskAndIntent(int taskId, Intent intent, int position, int division);
}

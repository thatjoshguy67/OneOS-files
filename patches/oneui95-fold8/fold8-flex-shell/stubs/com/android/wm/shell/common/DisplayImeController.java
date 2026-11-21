// Compile-time declarations for S948BXXU6ZZKN. Excluded from the patch DEX.
package com.android.wm.shell.common;
public class DisplayImeController {
    public interface ImePositionProcessor {
        default void onImeVisibilityChanged(int displayId, boolean showing) {}
    }
    public native void addPositionProcessor(ImePositionProcessor processor);
}

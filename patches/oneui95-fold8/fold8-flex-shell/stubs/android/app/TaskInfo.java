// Compile-time declarations for S948BXXU6ZZKN. Excluded from the patch DEX.
package android.app;
import android.content.ComponentName;
import android.content.Intent;
public class TaskInfo {
    public int displayId;
    public int taskId;
    public int userId;
    public ComponentName topActivity;
    public Intent baseIntent;
    public boolean originallySupportedMultiWindow;
    public native int getWindowingMode();
    public native int getActivityType();
}

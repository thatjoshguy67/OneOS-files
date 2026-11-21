// Compile-time declarations for S948BXXU6ZZKN. Excluded from the patch DEX.
package android.hardware.devicestate;
import java.util.concurrent.Executor;
public final class DeviceStateManager {
    public interface DeviceStateCallback {
        void onDeviceStateChanged(DeviceState state);
    }
    public native void registerCallback(Executor executor, DeviceStateCallback callback);
}

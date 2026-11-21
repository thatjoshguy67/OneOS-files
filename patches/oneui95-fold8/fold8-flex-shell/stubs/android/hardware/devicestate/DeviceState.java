// Compile-time declarations for S948BXXU6ZZKN. Excluded from the patch DEX.
package android.hardware.devicestate;
import java.util.Set;
public final class DeviceState {
    public static final class Configuration {
        public native Set<Integer> getPhysicalProperties();
    }
    public native int getIdentifier();
    public native Configuration getConfiguration();
}

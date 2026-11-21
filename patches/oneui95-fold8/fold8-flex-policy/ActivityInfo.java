package android.content.pm;

/** Compile-time declarations for the hidden methods in the pinned donor framework. */
public class ActivityInfo extends ComponentInfo {
    public int resizeMode;

    public static boolean isResizeableMode(int mode) {
        throw new UnsupportedOperationException();
    }

    public static boolean isPreserveOrientationMode(int mode) {
        throw new UnsupportedOperationException();
    }

    public boolean supportsPictureInPicture() {
        throw new UnsupportedOperationException();
    }
}

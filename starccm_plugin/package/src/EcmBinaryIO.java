import java.io.*;
import java.nio.*;
import java.nio.file.*;

/**
 * Binary I/O for the ECM coupling protocol (matches docs/IO_FORMAT.md).
 *
 * Header layout (v1 base = 44 bytes, v2 adds 8-byte stepId = 52 bytes total):
 *   char[8]  magic     "ECMIOv1\0"
 *   uint32   fileType  1=input, 2=output
 *   uint32   version   1
 *   uint32   N         number of coupled records
 *   double   time      simulation time [s]
 *   double   deltaT    timestep size [s]
 *   uint32   keyMode   0=globalCellId
 *   uint32   nInputs   0 for lumped (no extra electrical inputs)
 *   uint64   stepId    transaction ID (v2 extension)
 *
 * Each record:
 *   int32    key       cell/element id
 *   double   value     T [K] for input, qVol [W/m3] for output
 *
 * All values are little-endian (Java ByteBuffer with LITTLE_ENDIAN).
 * Atomic write: write to .tmp, then rename to .bin.
 */
public class EcmBinaryIO {

    private static final byte[] MAGIC         = {'E','C','M','I','O','v','1','\0'};
    private static final int    FILE_TYPE_IN  = 1;
    private static final int    FILE_TYPE_OUT = 2;
    private static final int    VERSION       = 1;
    private static final int    KEY_MODE_GLOBAL = 0;

    // Header sizes
    private static final int HEADER_V1_BYTES = 44;  // base header
    private static final int STEP_ID_BYTES   = 8;   // v2 stepId extension
    private static final int RECORD_BYTES    = 12;  // int32 key + double value

    /**
     * Write lumped ECM input file (N=1 record, nInputs=0).
     *
     * @param path    destination path (e.g. "ecm/ecm_in.bin")
     * @param stepId  transaction counter; ECM must echo this back
     * @param tEff    volume-averaged temperature [K]
     * @param time    current simulation time [s]
     * @param deltaT  timestep size [s]
     */
    public static void writeLumpedInput(String path, long stepId,
            double tEff, double time, double deltaT) throws IOException {

        int totalBytes = HEADER_V1_BYTES + STEP_ID_BYTES + RECORD_BYTES;
        ByteBuffer buf = ByteBuffer.allocate(totalBytes);
        buf.order(ByteOrder.LITTLE_ENDIAN);

        // magic[8]
        buf.put(MAGIC);
        // fileType, version, N
        buf.putInt(FILE_TYPE_IN);
        buf.putInt(VERSION);
        buf.putInt(1); // N = 1 record
        // time, deltaT
        buf.putDouble(time);
        buf.putDouble(deltaT);
        // keyMode, nInputs
        buf.putInt(KEY_MODE_GLOBAL);
        buf.putInt(0); // no extra electrical inputs
        // stepId (v2)
        buf.putLong(stepId);
        // single record: key=0, T=tEff
        buf.putInt(0);
        buf.putDouble(tEff);

        atomicWrite(path, buf.array());
    }

    /**
     * Read lumped ECM output file and return qVol [W/m3].
     * Validates the echoed stepId. Returns Double.NaN on mismatch.
     *
     * @param path           path to ecm_out.bin
     * @param expectedStepId stepId written in the corresponding input
     */
    public static double readLumpedOutput(String path, long expectedStepId) throws IOException {
        byte[] data = Files.readAllBytes(Paths.get(path));
        ByteBuffer buf = ByteBuffer.wrap(data);
        buf.order(ByteOrder.LITTLE_ENDIAN);

        // Skip magic[8]
        buf.position(8);
        // fileType, version, N
        buf.getInt(); // fileType (should be 2)
        buf.getInt(); // version
        int n = buf.getInt();
        // time, deltaT
        buf.getDouble();
        buf.getDouble();
        // keyMode, nInputs
        buf.getInt();
        int nInputs = buf.getInt();
        // stepId (v2)
        long echoedStepId = buf.getLong();

        if (echoedStepId != expectedStepId) {
            return Double.NaN; // caller should keep previous qVol
        }

        // skip any electrical input records that the ECM echoes back
        for (int i = 0; i < nInputs; i++) {
            int nameLen = buf.getInt();
            buf.position(buf.position() + nameLen + 8); // name + double value
        }

        // first output record: key + qVol
        buf.getInt(); // key
        return buf.getDouble();
    }

    // --- private helpers ---

    private static void atomicWrite(String path, byte[] data) throws IOException {
        String tmp = path + ".tmp";
        Files.write(Paths.get(tmp), data);
        Files.move(Paths.get(tmp), Paths.get(path), StandardCopyOption.REPLACE_EXISTING);
    }
}

import java.io.*;
import java.nio.*;
import java.nio.file.*;

/**
 * Binary I/O for the ECM coupling protocol (matches docs/IO_FORMAT.md).
 *
 * Header layout (v2, 52 bytes):
 *   char[8]  magic     "ECMIOv1\0"
 *   uint32   fileType  1=input, 2=output
 *   uint32   version   2
 *   uint32   N         number of coupled records
 *   double   time      simulation time [s]
 *   double   deltaT    timestep size [s]
 *   uint32   keyMode   0=globalCellId
 *   uint32   nInputs   number of named electrical inputs
 *   uint64   stepId    transaction ID (v2 extension)
 *
 * After header: nInputs records, each:
 *   uint32   nameLen
 *   char[nameLen] name  (UTF-8)
 *   double   value
 *
 * Then N cell records:
 *   int32    key       cell/element id
 *   double   value     T [K] for input, qVol [W/m3] for output
 *
 * All values little-endian.
 * Atomic write: write to .tmp, then rename to .bin.
 */
public class EcmBinaryIO {

    private static final byte[] MAGIC           = {'E','C','M','I','O','v','1','\0'};
    private static final int    FILE_TYPE_IN    = 1;
    private static final int    FILE_TYPE_OUT   = 2;
    private static final int    VERSION         = 2;
    private static final int    KEY_MODE_GLOBAL = 0;

    private static final int HEADER_V2_BYTES = 52;  // 44 base + 8 stepId
    private static final int RECORD_BYTES    = 12;  // int32 key + double value

    /**
     * Write lumped ECM input file: N=1 cell record, plus one "current_A" input.
     *
     * @param path      destination path (e.g. "ecm/ecm_in.bin")
     * @param stepId    transaction counter; ECM echoes this back
     * @param tEff      volume-averaged temperature [K]
     * @param time      current simulation time [s]
     * @param deltaT    timestep size [s]
     * @param currentA  discharge current [A]  (positive = discharging)
     */
    public static void writeLumpedInput(String path, long stepId,
            double tEff, double time, double deltaT, double currentA) throws IOException {

        byte[] nameBytes;
        try   { nameBytes = "current_A".getBytes("UTF-8"); }
        catch (UnsupportedEncodingException e) { nameBytes = "current_A".getBytes(); }

        // 1 input record: uint32 nameLen + name bytes + double value
        int inputBytes = 4 + nameBytes.length + 8;
        int totalBytes = HEADER_V2_BYTES + inputBytes + RECORD_BYTES;

        ByteBuffer buf = ByteBuffer.allocate(totalBytes);
        buf.order(ByteOrder.LITTLE_ENDIAN);

        // v2 header
        buf.put(MAGIC);
        buf.putInt(FILE_TYPE_IN);
        buf.putInt(VERSION);
        buf.putInt(1);              // N = 1 coupled cell record
        buf.putDouble(time);
        buf.putDouble(deltaT);
        buf.putInt(KEY_MODE_GLOBAL);
        buf.putInt(1);              // nInputs = 1 (current_A)
        buf.putLong(stepId);

        // electrical input record
        buf.putInt(nameBytes.length);
        buf.put(nameBytes);
        buf.putDouble(currentA);

        // cell record: key=0, T=tEff
        buf.putInt(0);
        buf.putDouble(tEff);

        atomicWrite(path, buf.array());
    }

    /**
     * Read lumped ECM output file; return qVol [W/m3].
     * Validates echoed stepId. Returns Double.NaN on stepId mismatch.
     */
    public static double readLumpedOutput(String path, long expectedStepId) throws IOException {
        byte[] data = Files.readAllBytes(Paths.get(path));
        ByteBuffer buf = ByteBuffer.wrap(data);
        buf.order(ByteOrder.LITTLE_ENDIAN);

        buf.position(8);     // skip magic
        buf.getInt();        // fileType
        buf.getInt();        // version
        buf.getInt();        // N
        buf.getDouble();     // time
        buf.getDouble();     // deltaT
        buf.getInt();        // keyMode
        int nInputs = buf.getInt();
        long echoedStepId = buf.getLong();

        if (echoedStepId != expectedStepId) {
            return Double.NaN;
        }

        // skip echoed input records
        for (int i = 0; i < nInputs; i++) {
            int nameLen = buf.getInt();
            buf.position(buf.position() + nameLen + 8);
        }

        buf.getInt();           // key
        return buf.getDouble(); // qVol [W/m3]
    }

    // -------------------------------------------------------------------------

    private static void atomicWrite(String path, byte[] data) throws IOException {
        Path dest = Paths.get(path);
        Path tmp  = Paths.get(path + ".tmp");
        if (dest.getParent() != null) {
            Files.createDirectories(dest.getParent());
        }
        Files.write(tmp, data);
        Files.move(tmp, dest, StandardCopyOption.REPLACE_EXISTING);
    }
}

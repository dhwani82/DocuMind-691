import java.nio.file.Files;
import java.nio.file.Paths;

public class Mixed {
    public static String loadConfig(String path) throws Exception {
        return Files.readString(Paths.get(path));
    }

    public static void saveResult(String data, String filename) throws Exception {
        Files.writeString(Paths.get(filename), data);
    }

    public static class DataProcessor {
        public String process(String raw) {
            return raw.trim().toLowerCase();
        }

        public boolean validate(String data) {
            return data.length() > 0;
        }
    }
}

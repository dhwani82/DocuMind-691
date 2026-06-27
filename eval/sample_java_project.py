"""Sample Java project used for DocuMind demos and indexing."""

from __future__ import annotations

from pathlib import Path

SAMPLE_CALLS = """
public class Calls {
    public static int helper() {
        return 1;
    }

    public static int mainFlow() {
        return helper();
    }
}
"""

SAMPLE_CALCULATOR = """
public class Calculator {
    private int value = 0;

    public int add(int x, int y) {
        return x + y;
    }

    public int subtract(int x, int y) {
        return x - y;
    }

    public void reset() {
        this.value = 0;
    }
}
"""

SAMPLE_INHERITANCE = """
public class Animal {
    public String speak() {
        return "sound";
    }
}

class Dog extends Animal {
    @Override
    public String speak() {
        return "Woof";
    }
}

class Cat extends Animal {
    @Override
    public String speak() {
        return "Meow";
    }
}
"""

SAMPLE_MIXED = """
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
"""

SAMPLE_SIMPLE = """
public class Simple {
    public static int testFunction(int x) {
        if (x > 0) {
            return 1;
        }
        return 0;
    }

    public static int loopExample(int[] items) {
        int count = 0;
        for (int item : items) {
            if (item > 5) {
                count++;
            }
        }
        return count;
    }
}
"""

SAMPLE_INSTANCE_USAGE = """
public class InstanceUsage {
    public static int useViaInstance() {
        Calculator calc = new Calculator();
        return calc.add(1, 2);
    }
}
"""

SAMPLE_FILES = {
    "Calls.java": SAMPLE_CALLS,
    "Calculator.java": SAMPLE_CALCULATOR,
    "inheritance.java": SAMPLE_INHERITANCE,
    "Mixed.java": SAMPLE_MIXED,
    "Simple.java": SAMPLE_SIMPLE,
    "InstanceUsage.java": SAMPLE_INSTANCE_USAGE,
}


def ensure_sample_java_project(target_dir: Path) -> Path:
    """Materialize the Java sample project on disk."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for name, content in SAMPLE_FILES.items():
        path = target_dir / name
        path.write_text(content.strip() + "\n", encoding="utf-8")
    return target_dir.resolve()

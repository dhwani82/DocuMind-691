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

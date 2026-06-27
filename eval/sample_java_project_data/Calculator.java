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

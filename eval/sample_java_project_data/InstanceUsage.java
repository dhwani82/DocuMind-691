public class InstanceUsage {
    public static int useViaInstance() {
        Calculator calc = new Calculator();
        return calc.add(1, 2);
    }
}

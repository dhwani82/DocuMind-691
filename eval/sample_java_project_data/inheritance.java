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

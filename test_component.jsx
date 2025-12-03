import React, { useState, useEffect } from 'react';
import './App.css';

// Regular JavaScript function
function calculateSum(a, b) {
    return a + b;
}

// Arrow function
const formatDate = (date) => {
    return date.toLocaleDateString();
};

// React functional component
function App() {
    const [count, setCount] = useState(0);
    
    useEffect(() => {
        document.title = `Count: ${count}`;
    }, [count]);
    
    const handleClick = () => {
        setCount(count + 1);
    };
    
    return (
        <div className="App">
            <h1>Counter App</h1>
            <p>Count: {count}</p>
            <button onClick={handleClick}>Increment</button>
        </div>
    );
}

// React arrow function component
const Button = ({ label, onClick }) => {
    return (
        <button onClick={onClick} className="btn">
            {label}
        </button>
    );
};

// Export default component
export default App;

// Named export
export { Button, calculateSum };


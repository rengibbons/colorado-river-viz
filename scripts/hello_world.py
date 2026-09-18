import matplotlib.pyplot as plt

from myproject import hello_world

data = hello_world()

plt.hist(data, bins=20)
plt.title("Hello from the myproject package")
plt.xlabel("Value")
plt.ylabel("Count")
plt.tight_layout()
plt.savefig("hello_world.png")

print(f"Generated {len(data)} data points. Plot saved to hello_world.png.")

import tkinter as tk
from gui.app import App




def main():
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    print("Arrancando aplicación…")
    main()

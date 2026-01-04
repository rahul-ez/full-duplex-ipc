import tkinter as tk
import threading
import sys
import posix_ipc

HIGHLIGHT_DURATION_MS = 700

class IPCVisualizer:
    def __init__(self, root, self_name, peer_name):
        self.root = root
        self.self_name = self_name
        self.peer_name = peer_name
        root.title(f"Visualizer — {self_name}")

        self.sent_count = 0
        self.recv_count = 0

        # --- UI SETUP ---
        self.canvas = tk.Canvas(root, width=700, height=180, bg="white")
        self.canvas.pack(pady=5)
        
        # Entities & Arrows
        self.canvas.create_rectangle(50, 60, 200, 120, fill="#e3f2fd", outline="#1976d2")
        self.canvas.create_rectangle(500, 60, 650, 120, fill="#e8f5e9", outline="#388e3c")
        self.canvas.create_text(125, 90, text=self_name, font=("Arial", 10, "bold"))
        self.canvas.create_text(575, 90, text=peer_name, font=("Arial", 10, "bold"))
        self.arrow_out = self.canvas.create_line(200, 80, 500, 80, arrow=tk.LAST, width=3, fill="gray")
        self.arrow_in = self.canvas.create_line(500, 100, 200, 100, arrow=tk.LAST, width=3, fill="gray")

        # Center Input Bar
        input_frame = tk.Frame(root)
        input_frame.pack(pady=10, fill=tk.X)
        
        # Internal frame to center elements
        center_container = tk.Frame(input_frame)
        center_container.pack(expand=True)
        
        self.entry = tk.Entry(center_container, width=50)
        self.entry.pack(side=tk.LEFT, padx=5)
        self.entry.bind("<Return>", lambda e: self.send_message())
        
        send_btn = tk.Button(center_container, text="Send", command=self.send_message, bg="#e0e0e0")
        send_btn.pack(side=tk.LEFT)

        # Stats
        self.stats_label = tk.Label(root, text="Sent: 0 | Received: 0", font=("Arial", 9, "italic"), fg="gray")
        self.stats_label.pack()

        # Chat Log with Alignment Tags
        self.log = tk.Text(root, height=12, width=80, state=tk.DISABLED, padx=10, pady=10)
        self.log.pack(padx=20, pady=10)
        
        # Tag configuration: "sent" aligns right, "received" aligns left
        self.log.tag_config("sent", justify='right', foreground="#0b8043")
        self.log.tag_config("received", justify='left', foreground="#1976d2")

        # Connect to Local C Backend
        try:
            self.mq_to_c = posix_ipc.MessageQueue(f"/mq_gui_tx_{self_name}")
            self.mq_from_c = posix_ipc.MessageQueue(f"/mq_gui_rx_{self_name}")
        except Exception as e:
            print(f"Error: Connect to C backend first.\n{e}")
            sys.exit(1)

        threading.Thread(target=self.receive_loop, daemon=True).start()

    def update_stats_label(self):
        self.stats_label.config(text=f"Sent: {self.sent_count} | Received: {self.recv_count}")

    def send_message(self):
        msg = self.entry.get().strip()
        if msg:
            self.mq_to_c.send(msg.encode())
            self.entry.delete(0, tk.END)

    def receive_loop(self):
        while True:
            try:
                msg, _ = self.mq_from_c.receive()
                text = msg.decode('utf-8').strip('\x00')
                
                if text.startswith(f"[{self.self_name}]"):
                    self.sent_count += 1
                    # Pass the "sent" tag
                    self.root.after(0, lambda t=text: self.display(t, "#0b8043", self.arrow_out, "sent"))
                else:
                    self.recv_count += 1
                    # Pass the "received" tag
                    self.root.after(0, lambda t=text: self.display(t, "blue", self.arrow_in, "received"))
                
                self.root.after(0, self.update_stats_label)
            except:
                break

    def display(self, text, color, arrow, tag):
        self.log.config(state=tk.NORMAL)
        # Apply the alignment tag here
        self.log.insert(tk.END, text + "\n", tag)
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)
        
        self.canvas.itemconfig(arrow, fill=color)
        self.root.after(HIGHLIGHT_DURATION_MS, lambda: self.canvas.itemconfig(arrow, fill="gray"))

if __name__ == "__main__":
    root = tk.Tk()
    app = IPCVisualizer(root, sys.argv[1], sys.argv[2])
    root.mainloop()
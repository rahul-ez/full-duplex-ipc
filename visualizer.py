import tkinter as tk
import time
import threading
import os

LOG_FILE = "ipc_log.txt"
HIGHLIGHT_DURATION_MS = int(os.environ.get("HIGHLIGHT_DURATION_MS", "1000"))

class IPCVisualizer:
    def __init__(self, root):
        self.root = root
        root.title("Full-Duplex IPC Visualizer")

        self.canvas = tk.Canvas(root, width=700, height=300, bg="white")
        self.canvas.pack()

        # Draw process boxes
        self.procA = self.canvas.create_rectangle(50, 100, 200, 180, fill="#e3f2fd")
        self.procB = self.canvas.create_rectangle(500, 100, 650, 180, fill="#e8f5e9")

        self.canvas.create_text(125, 140, text="Process A", font=("Arial", 12, "bold"))
        self.canvas.create_text(575, 140, text="Process B", font=("Arial", 12, "bold"))

        # Arrows
        self.arrow_ab = self.canvas.create_line(200, 140, 500, 140,
                                                arrow=tk.LAST, width=3, fill="gray")
        self.arrow_ba = self.canvas.create_line(500, 160, 200, 160,
                                                arrow=tk.LAST, width=3, fill="gray")

        self.status = tk.Label(root, text="Waiting for IPC events...", font=("Arial", 11))
        self.status.pack(pady=10)

        # Message area: show recent [SEND] and [RECV] messages
        self.log_frame = tk.Frame(root)
        self.log_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0,10))

        self.log_text = tk.Text(self.log_frame, height=6, width=88, state=tk.DISABLED, wrap=tk.NONE)
        self.log_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        scrollbar = tk.Scrollbar(self.log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        # Tags for coloring
        self.log_text.tag_config('send', foreground='green')
        self.log_text.tag_config('recv', foreground='orange')
        self.log_text.tag_config('info', foreground='black')

        # Track scheduled after callbacks so we can cancel/reset them and ensure
        # only one arrow is highlighted at a time.
        self._after_ids = {}

        self.last_size = 0
        threading.Thread(target=self.watch_log, daemon=True).start()

    def flash_arrow(self, arrow, color):
        # Ensure any pending resets are cancelled and clear both arrows first
        for a in (self.arrow_ab, self.arrow_ba):
            after_id = self._after_ids.pop(a, None)
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except Exception:
                    pass
            # reset other arrow immediately
            self.canvas.itemconfig(a, fill="gray")

        # Highlight the requested arrow and schedule a reset
        self.canvas.itemconfig(arrow, fill=color)
        after_id = self.root.after(HIGHLIGHT_DURATION_MS, lambda a=arrow: self._reset_arrow(a))
        self._after_ids[arrow] = after_id

    def _reset_arrow(self, arrow):
        # Callback to reset an arrow and clear its after id
        try:
            self.canvas.itemconfig(arrow, fill="gray")
        except Exception:
            pass
        self._after_ids.pop(arrow, None)

    def watch_log(self):
        while True:
            if os.path.exists(LOG_FILE):
                size = os.path.getsize(LOG_FILE)
                if size > self.last_size:
                    with open(LOG_FILE, "r") as f:
                        f.seek(self.last_size)
                        lines = f.readlines()
                        self.last_size = size
                        for line in lines:
                            self.process_event(line.strip())
            time.sleep(0.2)

    def process_event(self, event):
        # Update status text
        self.root.after(0, lambda: self.status.config(text=event))

        # Determine message type and direction
        tag = 'info'
        if "[SEND]" in event:
            tag = 'send'
            if "A->B" in event:
                self.root.after(0, lambda: self.flash_arrow(self.arrow_ab, "green"))
            elif "B->A" in event:
                self.root.after(0, lambda: self.flash_arrow(self.arrow_ba, "blue"))
        elif "[RECV]" in event:
            tag = 'recv'
            # Highlight arrow for a recv as well (subtle color)
            if "A->B" in event or "A<-B" in event:
                self.root.after(0, lambda: self.flash_arrow(self.arrow_ba, "orange"))
            elif "B->A" in event or "B<-A" in event:
                self.root.after(0, lambda: self.flash_arrow(self.arrow_ab, "orange"))

        # Append to message area
        self.root.after(0, lambda: self.append_message(event, tag))

    def append_message(self, text, tag='info'):
        # Insert a line into the read-only Text widget with the given tag
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, text + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

root = tk.Tk()
app = IPCVisualizer(root)
root.mainloop()

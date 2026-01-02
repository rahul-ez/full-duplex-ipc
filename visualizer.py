import tkinter as tk
import threading
import sys
import posix_ipc
import time

MQ_A_TO_B = "/mq_a_to_b"
MQ_B_TO_A = "/mq_b_to_a"
HIGHLIGHT_DURATION_MS = 700


def get_queue(name):
    try:
        return posix_ipc.MessageQueue(name)
    except posix_ipc.ExistentialError:
        return posix_ipc.MessageQueue(
            name,
            flags=posix_ipc.O_CREAT,
            max_messages=10,
            max_message_size=1024
        )


class IPCVisualizer:
    def __init__(self, root, role):
        self.root = root
        self.role = role
        root.title(f"IPC Full-Duplex Chat — Process {role}")

        # ================= Canvas =================
        self.canvas = tk.Canvas(root, width=700, height=260, bg="white")
        self.canvas.pack(pady=5)

        self.canvas.create_rectangle(50, 90, 200, 160, fill="#e3f2fd")
        self.canvas.create_rectangle(500, 90, 650, 160, fill="#e8f5e9")

        self.canvas.create_text(125, 125, text="Process A", font=("Arial", 12, "bold"))
        self.canvas.create_text(575, 125, text="Process B", font=("Arial", 12, "bold"))

        self.arrow_ab = self.canvas.create_line(
            200, 115, 500, 115, arrow=tk.LAST, width=3, fill="gray"
        )
        self.arrow_ba = self.canvas.create_line(
            500, 135, 200, 135, arrow=tk.LAST, width=3, fill="gray"
        )

        # ================= Chat =================
        self.log = tk.Text(root, height=10, width=90, state=tk.DISABLED)
        self.log.pack(padx=10, pady=5)

        self.log.tag_config(
            "incoming", justify="left",
            lmargin1=10, lmargin2=10, rmargin=120
        )
        self.log.tag_config(
            "outgoing", justify="right",
            lmargin1=120, lmargin2=120, rmargin=10,
            foreground="#0b8043"
        )

        # ================= Input =================
        frame = tk.Frame(root)
        frame.pack(pady=5)

        self.entry = tk.Entry(frame, width=70)
        self.entry.pack(side=tk.LEFT, padx=5)
        self.entry.bind("<Return>", lambda e: self.send_message())

        tk.Button(frame, text="Send", command=self.send_message).pack(side=tk.LEFT)

        # ================= Message Queues =================
        self.mq_a2b = get_queue(MQ_A_TO_B)
        self.mq_b2a = get_queue(MQ_B_TO_A)

        if role == "A":
            self.send_mq = self.mq_a2b
            self.recv_mq = self.mq_b2a
            self.peer = "B"
        else:
            self.send_mq = self.mq_b2a
            self.recv_mq = self.mq_a2b
            self.peer = "A"

        # ================= Receiver Thread =================
        threading.Thread(target=self.receive_loop, daemon=True).start()

    # ==================================================
    def send_message(self):
        msg = self.entry.get().strip()
        if not msg:
            return

        self.send_mq.send(msg.encode())
        self.entry.delete(0, tk.END)

        self.append(f"You: {msg}", "outgoing")

        if self.role == "A":
            self.flash(self.arrow_ab, "green")
        else:
            self.flash(self.arrow_ba, "blue")

    # ==================================================
    def receive_loop(self):
        while True:
            msg, _ = self.recv_mq.receive()  # blocking is OK in thread
            text = msg.decode()

            self.root.after(
                0,
                lambda t=text:
                self.append(f"{self.peer}: {t}", "incoming")
            )

            if self.role == "A":
                self.root.after(0, lambda: self.flash(self.arrow_ba, "blue"))
            else:
                self.root.after(0, lambda: self.flash(self.arrow_ab, "green"))

    # ==================================================
    def flash(self, arrow, color):
        self.canvas.itemconfig(self.arrow_ab, fill="gray")
        self.canvas.itemconfig(self.arrow_ba, fill="gray")
        self.canvas.itemconfig(arrow, fill=color)
        self.root.after(
            HIGHLIGHT_DURATION_MS,
            lambda: self.canvas.itemconfig(arrow, fill="gray")
        )

    # ==================================================
    def append(self, text, tag):
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, text + "\n\n", tag)
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)


# ======================= MAIN =========================
if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("A", "B"):
        print("Usage: python3 visualiser.py <A|B>")
        sys.exit(1)

    root = tk.Tk()
    IPCVisualizer(root, sys.argv[1])
    root.mainloop()

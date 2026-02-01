import tkinter as tk
import threading
import sys
import posix_ipc
import time
import queue

# Constants
REFRESH_MS = 100
HIGHLIGHT_DURATION_MS = 700

class EnhancedVisualizer:
    def __init__(self, root, self_name, peer_name):
        self.root = root
        self.self_name = self_name
        self.peer_name = peer_name
        
        self.root.title(f"Enhanced Visualizer — {self_name} (Monitor)")
        self.root.geometry("800x600")
        
        # Data
        self.sent_count = 0
        self.recv_count = 0
        self.cpu_owner = None # 'self', 'peer', or None
        self.process_states = {self.self_name: "RUNNING", self.peer_name: "RUNNING"} # RUNNING, BLOCKED

        # --- UI SETUP ---
        
        # 1. Canvas for Process/Kernel Visualization
        self.canvas = tk.Canvas(root, width=800, height=400, bg="white")
        self.canvas.pack(pady=5)
        
        # User Space Layer (Top)
        self.canvas.create_text(400, 20, text="USER SPACE", font=("Arial", 12, "bold"), fill="#555")
        
        # Kernel Space Layer (Bottom)
        self.kernel_boundary = self.canvas.create_line(0, 200, 800, 200, dash=(4, 4), width=2, fill="red")
        self.canvas.create_text(400, 220, text="KERNEL SPACE", font=("Arial", 12, "bold"), fill="#555")
        
        # Process Boxes
        # Self (Left)
        self.self_box = self.canvas.create_rectangle(50, 60, 250, 140, fill="#e8f5e9", outline="#388e3c", width=3)
        self.self_label = self.canvas.create_text(150, 100, text=f"Process {self_name}", font=("Arial", 12, "bold"))
        self.self_status = self.canvas.create_text(150, 125, text="RUNNING", font=("Arial", 9), fill="green")
        
        # Peer (Right) - We visualize peer as a box too, to show scheduling shifts
        self.peer_box = self.canvas.create_rectangle(550, 60, 750, 140, fill="#e3f2fd", outline="#1976d2", width=3)
        self.peer_label = self.canvas.create_text(650, 100, text=f"Process {peer_name}", font=("Arial", 12, "bold"))
        self.peer_status = self.canvas.create_text(650, 125, text="RUNNING", font=("Arial", 9), fill="blue")

        # Kernel Area Visuals
        self.kernel_box = self.canvas.create_rectangle(50, 240, 750, 360, fill="#333", outline="black")
        self.canvas.create_text(400, 300, text="OS KERNEL & DRIVERS", font=("Courier", 16, "bold"), fill="#ddd")
        
        # 2. Controls & Chat
        control_frame = tk.Frame(root)
        control_frame.pack(fill=tk.X, padx=10)
        
        tk.Label(control_frame, text="Chat Input:").pack(side=tk.LEFT)
        self.entry = tk.Entry(control_frame, width=30, font=("Arial", 12))
        self.entry.pack(side=tk.LEFT, padx=5)
        self.entry.bind("<Return>", lambda e: self.send_message())
        tk.Button(control_frame, text="Send", command=self.send_message, font=("Arial", 11)).pack(side=tk.LEFT)
        tk.Button(control_frame, text="Clear Logs", command=self.clear_logs, bg="#ffcdd2", font=("Arial", 11)).pack(side=tk.LEFT, padx=5)
        
        self.stats_label = tk.Label(control_frame, text="Sent: 0 | Recv: 0", font=("Arial", 11))
        self.stats_label.pack(side=tk.RIGHT)
        
        # 3. Log Window
        self.log_text = tk.Text(root, height=12, bg="#f0f0f0", font=("Consolas", 12)) # increased base font
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Tags for Alignment and Color - Bold and Larger
        self.log_text.tag_config("KERNEL", foreground="red", justify='center', font=("Consolas", 10))
        self.log_text.tag_config("SCHED", foreground="purple", font=("Consolas", 10, "bold"), justify='center')
        self.log_text.tag_config("SYNC", foreground="orange", justify='center', font=("Consolas", 10))
        
        # Chat messages bigger and bolder
        self.log_text.tag_config("SELF", foreground="#388e3c", justify='right', font=("Arial", 14, "bold")) 
        self.log_text.tag_config("PEER", foreground="#1976d2", justify='left', font=("Arial", 14, "bold"))  

        # --- LOGIC SETUP ---
        self.pid_map = {} # pid -> name
        
        # Connect to MQ
        try:
            self.mq_to_c = posix_ipc.MessageQueue(f"/mq_gui_tx_{self_name}")
            self.mq_from_c = posix_ipc.MessageQueue(f"/mq_gui_rx_{self_name}")
            self.log_message(f"[System] Connected to MQ /mq_gui_*_{self_name}", "KERNEL")
        except Exception as e:
            self.log_message(f"[Error] Failed to connect to MQs: {e}", "KERNEL")
            
        # Start Threads
        self.running = True
        threading.Thread(target=self.receive_loop, daemon=True).start()
        threading.Thread(target=self.log_watcher_loop, daemon=True).start()

    def clear_logs(self):
        self.log_text.delete('1.0', tk.END)

    def send_message(self):
        msg = self.entry.get().strip()
        if msg and hasattr(self, 'mq_to_c'):
            try:
                self.mq_to_c.send(msg.encode())
                self.entry.delete(0, tk.END)
            except Exception as e:
                self.log_message(f"[Error] Send failed: {e}", "SELF")

    def receive_loop(self):
        if not hasattr(self, 'mq_from_c'): return
        while self.running:
            try:
                msg, _ = self.mq_from_c.receive()
                text = msg.decode('utf-8').strip('\x00')
                is_self = text.startswith(f"[{self.self_name}]")
                
                if is_self:
                    self.sent_count += 1
                    tag = "SELF"
                else:
                    self.recv_count += 1
                    tag = "PEER"
                
                self.root.after(0, self.update_stats)
                self.root.after(0, lambda t=text, g=tag: self.log_message(t, g))
                self.root.after(0, lambda s=is_self: self.animate_ipc(s))
                
            except Exception as e:
                if self.running: self.log_message(f"[MQ Error] {e}", "KERNEL")
                break

    def update_stats(self):
        self.stats_label.config(text=f"Sent: {self.sent_count} | Recv: {self.recv_count}")

    def log_message(self, text, tag):
        self.log_text.insert(tk.END, text + "\n", tag)
        self.log_text.see(tk.END)

    def log_watcher_loop(self):
        # Tails 'ipc_log.txt'
        filename = "ipc_log.txt"
        while self.running:
            try:
                f = open(filename, "r")
                break
            except:
                time.sleep(1)
        
        # Scan file from start to capture META tags
        f.seek(0, 0)

        while self.running:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            
            line = line.strip()
            self.root.after(0, lambda l=line: self.process_log_entry(l))

    def process_log_entry(self, line):
        # [META] pid=1234 name=a
        if "[META]" in line:
            parts = {}
            for part in line.split(" "):
                if "=" in part:
                    k, v = part.split("=", 1)
                    parts[k] = v
            pid = parts.get("pid")
            name = parts.get("name")
            if pid and name:
                self.pid_map[pid] = name
                print(f"Mapped PID {pid} to {name}")

        elif "[KERNEL]" in line:
            self.log_message(line, "KERNEL")
            
            parts = {}
            for part in line.split(" "):
                if "=" in part:
                    k, v = part.split("=", 1)
                    parts[k] = v
            
            syscall = parts.get("syscall")
            status = parts.get("status")
            pid = parts.get("pid")
            
            # Determine target from PID map
            target = "self" 
            proc_name = self.pid_map.get(pid)
            
            if proc_name == self.peer_name:
                target = "peer"
            elif proc_name == self.self_name:
                target = "self"
            
            # Only block/unblock if we know who it is or it's definitely our strace
            if status == "START_BLOCK":
                self.set_state(target, "BLOCKED")
                self.log_message(f"[SCHED] Process {proc_name or pid} yielded CPU (Blocking on {syscall})", "SCHED")
                self.log_message(f"[SYNC] {proc_name or pid} waiting on {syscall}", "SYNC")
                self.flash_kernel_boundary()
                
            elif status == "END_BLOCK":
                self.set_state(target, "RUNNING")
                self.log_message(f"[SCHED] Process {proc_name or pid} scheduled (Resumed from {syscall})", "SCHED")
                self.log_message(f"[SYNC] {proc_name or pid} acquired resource / unblocked", "SYNC")

    def set_state(self, target, state):
        color = "#ffeb3b" if state == "BLOCKED" else "#e8f5e9" if target == "self" else "#e3f2fd"
        status_text = "BLOCKED (Yellow)" if state == "BLOCKED" else "RUNNING"
        status_color = "orange" if state == "BLOCKED" else "green" if target == "self" else "blue"
        
        box = self.self_box if target == "self" else self.peer_box
        label = self.self_status if target == "self" else self.peer_status
        
        # Keep original colors for running
        if state == "RUNNING":
             color = "#e8f5e9" if target == "self" else "#e3f2fd"
             
        self.canvas.itemconfig(box, fill=color)
        self.canvas.itemconfig(label, text=status_text, fill=status_color)
            
    # Removed animate_cpu_switch
        


    def flash_kernel_boundary(self):
        self.canvas.itemconfig(self.kernel_boundary, width=4, fill="orange")
        self.root.after(300, lambda: self.canvas.itemconfig(self.kernel_boundary, width=2, fill="red"))
    
    def animate_ipc(self, is_self):
        # An arrow crossing into kernel
        x_start = 150 if is_self else 650
        x_end = 650 if is_self else 150
        
        # Draw arrow dipping into kernel
        # Path: Start -> Kernel(Mid) -> End
        # We simulate this with a line
        arrow = self.canvas.create_line(x_start, 140, 400, 240, width=3, fill="blue", arrow=tk.LAST)
        self.root.after(500, lambda: self.canvas.delete(arrow))
        
        arrow2 = self.canvas.create_line(400, 240, x_end, 140, width=3, fill="blue", arrow=tk.LAST)
        self.root.after(500, lambda: self.canvas.delete(arrow2))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 enhanced_visualizer.py <self_name> <peer_name>")
        # Default for testing
        sys.argv = [sys.argv[0], "a", "b"]
        
    root = tk.Tk()
    app = EnhancedVisualizer(root, sys.argv[1], sys.argv[2])
    root.mainloop()

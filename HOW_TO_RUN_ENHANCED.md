# How to Run Enhanced Visualization

This project includes an enhanced visualizer that shows User/Kernel space transitions, CPU scheduling, and synchronization states using `strace` logs.

## Prerequisites
- Linux Environment
- `strace` installed
- `python3` with `tkinter` and `posix_ipc`

## Step 1: Compile the Chat Application
Compile the `chat.c` as usual (no changes were made to it):
```bash
gcc chat.c -o chat -lrt -lpthread
```

## Step 2: Clean Old Logs
To ensure the visualizer maps processes correctly (A vs B), clear the log file before a new session:
```bash
rm -f ipc_log.txt
```

## Step 3: Run Chat with Strace (Terminal 1 - User A)
Run `chat` for user A, capturing its execution (including startup) to `strace_a.out`.
```bash
strace -f -o strace_a.out ./chat a b
```

## Step 4: Run Chat with Strace (Terminal 2 - User B)
Run `chat` for user B, capturing its execution to `strace_b.out`.
```bash
strace -f -o strace_b.out ./chat b a
```

## Step 5: Start Strace Parsers (Terminals 3 & 4)
We need parsers for **both** outputs to feed the single `ipc_log.txt`.

**Terminal 3 (Parser for A):**
```bash
python3 strace_parser.py strace_a.out
```

**Terminal 4 (Parser for B):**
```bash
python3 strace_parser.py strace_b.out
```

*(Note: You can run these in the background if you prefer)*

## Step 6: Run the Enhanced Visualizer (Terminal 5 & 6)
Start the visualizer for each user.

**Terminal 5 (Visualizer A):**
```bash
python3 enhanced_visualizer.py a b
```

**Terminal 6 (Visualizer B):**
```bash
python3 enhanced_visualizer.py b a
```

## Features
- **Global Clear Button**: Clears the visualizer log window.
- **Chat Layout**: 
    - Self messages on the **Right** (Green).
    - Peer messages on the **Left** (Blue).
    - Kernel logs in the **Center** (Red).
- **CPU Scheduling**: 
    - CPU icon moves to "Process A" or "Process B" based on real system calls.
    - CPU moves to "Kernel" during blocking calls.

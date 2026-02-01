import re
import sys
import time
import os

class StraceParser:
    def __init__(self, input_file, output_file):
        self.input_file = input_file
        self.output_file = output_file
        self.running = True

    def parse_line(self, line):
        # Regex to capture PID, call, and status (unfinished/resumed/complete)
        # Format examples:
        # [pid 1234] 10:00:00 read(0,  <unfinished ...>
        # [pid 1234] 10:00:01 <... read resumed> "buf", 100) = 4
        # [pid 1234] 10:00:02 write(1, "msg", 3) = 3
        
        # Simple detection of blocking calls
        # We look for "unfinished" indicating waiting, and "resumed" indicating wake up.
        
        timestamp = time.strftime("%H:%M:%S") # Placeholder if strace doesn't have it
        
        # Extract PID if present (strace -f)
        pid_match = re.search(r'(?:^|\[pid\s+)(\d+)\]?', line)
        pid = pid_match.group(1) if pid_match else "UNKNOWN"
        
        log_entry = None
        
        if "unfinished" in line:
            # Start of a potentially blocking call
            # Extract syscall name
            call_match = re.search(r'([a-zA-Z0-9_]+)\(', line)
            if call_match:
                syscall = call_match.group(1)
                log_entry = f"[KERNEL] syscall={syscall} pid={pid} status=START_BLOCK"
        
        elif "resumed" in line:
            # End of blocking call
            # Extract syscall name from <... syscall resumed>
            call_match = re.search(r'<\.\.\.\s+([a-zA-Z0-9_]+)\s+resumed>', line)
            if call_match:
                syscall = call_match.group(1)
                log_entry = f"[KERNEL] syscall={syscall} pid={pid} status=END_BLOCK"
        
        else:
            # Instantaneous or complete call
            call_match = re.search(r'([a-zA-Z0-9_]+)\(', line)
            if call_match:
                syscall = call_match.group(1)
                # Filter for relevant syscalls to avoid noise
                if syscall in ['read', 'write', 'sem_wait', 'sem_post', 'mq_timedsend', 'mq_timedreceive', 'fork', 'clone', 'wait4']:
                     log_entry = f"[KERNEL] syscall={syscall} pid={pid} status=COMPLETE"

        if log_entry:
            # Filtering Logic
            if log_entry == self.last_entry:
                return None
            # 2. Filter out noisy 'write' calls to stdout/stderr (fd 1 or 2) to reduce clutter
            # We want to see significant IPC writes, but maybe not every printf
            if "syscall=write" in log_entry:
                return None
            self.last_entry = log_entry
            
        # 3. Detect execve to map PID to Name (for the visualizer)
        # matches: execve("./chat", ["./chat", "a", "b"], ...
        if "execve" in line:
            # Try to grab the args
            # Regex: ["./chat", "arg1", "arg2"]
            args_match = re.search(r'\["[^"]*chat",\s*"([^"]+)",\s*"([^"]+)"\]', line)
            if args_match:
                name = args_match.group(1) # 'a'
                log_entry = f"[META] pid={pid} name={name}"

        return log_entry

    def process(self):
        self.last_entry = None
        # Open output file in append mode
        with open(self.output_file, 'a', buffering=1) as out_f:
            # Follow input file (tail behavior)
            current_file = open(self.input_file, 'r')
            # Seek to end? No, we might want history if available. 
            # But usually we run this with the app. Let's start from end to avoid old logs?
            # User didn't specify. I'll read from current pos.
            current_file.seek(0, 2) 
            
            while self.running:
                where = current_file.tell()
                line = current_file.readline()
                if not line:
                    time.sleep(0.1)
                    current_file.seek(where)
                else:
                    entry = self.parse_line(line)
                    if entry:
                        out_f.write(f"{entry}\n")
                        out_f.flush()
                        os.fsync(out_f.fileno())
                        print(entry) # Debug to stdout

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 strace_parser.py <strace_output_file>")
        sys.exit(1)
    
    input_log = sys.argv[1]
    output_log = "ipc_log.txt"
    
    print(f"Parsing {input_log} -> {output_log}")
    parser = StraceParser(input_log, output_log)
    try:
        parser.process()
    except KeyboardInterrupt:
        print("Stopping parser...")

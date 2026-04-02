import psutil
import time
import os
import sys
from datetime import datetime

class ResourceMonitor:
    def __init__(self, interval=2):
        self.interval = interval
        self.stats = {
            "api": {"cpu": [], "memory": []},
            "worker": {"cpu": [], "memory": []},
            "system": {"cpu": [], "memory": []}
        }
        self.start_time = None

    def find_processes(self):
        """Find PIDs for Uvicorn and Arq processes."""
        api_pids = []
        worker_pids = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if not cmdline:
                    continue
                cmd_str = " ".join(cmdline).lower()
                
                # Check for Uvicorn (FastAPI)
                if "uvicorn" in cmd_str and "app.main:app" in cmd_str:
                    api_pids.append(proc.pid)
                
                # Check for Arq (Worker)
                if "arq" in cmd_str and "app.workers.rag_worker.worker" in cmd_str.replace("_", "."):
                    worker_pids.append(proc.pid)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        return api_pids, worker_pids

    def get_proc_stats(self, pids):
        cpu_sum = 0.0
        mem_sum = 0.0
        active_count = 0
        
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                if proc.is_running():
                    # cpu_percent(interval=None) returns since last call
                    cpu_sum += proc.cpu_percent(interval=None)
                    mem_sum += proc.memory_info().rss / (1024 * 1024)  # MB
                    active_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return cpu_sum, mem_sum, active_count

    def run(self):
        print("\n" + "="*50)
        print("🚀 CLAIMLY RESOURCE MONITOR STARTING...")
        print("Press Ctrl+C to stop and see summary.")
        print("="*50 + "\n")
        
        self.start_time = datetime.now()
        
        # Initialize CPU usage baseline
        psutil.cpu_percent(interval=None)
        
        try:
            while True:
                api_pids, worker_pids = self.find_processes()
                
                api_cpu, api_mem, api_count = self.get_proc_stats(api_pids)
                worker_cpu, worker_mem, worker_count = self.get_proc_stats(worker_pids)
                sys_cpu = psutil.cpu_percent(interval=None)
                sys_mem = psutil.virtual_memory().percent
                
                # Store stats
                if api_count > 0:
                    self.stats["api"]["cpu"].append(api_cpu)
                    self.stats["api"]["memory"].append(api_mem)
                
                if worker_count > 0:
                    self.stats["worker"]["cpu"].append(worker_cpu)
                    self.stats["worker"]["memory"].append(worker_mem)
                
                self.stats["system"]["cpu"].append(sys_cpu)
                
                # Print current status
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}]")
                print(f"  🏢 API ({api_count} proc): CPU: {api_cpu:5.1f}% | RAM: {api_mem:7.1f} MB")
                print(f"  👷 Worker ({worker_count} proc): CPU: {worker_cpu:5.1f}% | RAM: {worker_mem:7.1f} MB")
                print(f"  💻 System Total: CPU: {sys_cpu:5.1f}% | Global RAM: {sys_mem:4.1f}%")
                print("-" * 30)
                
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            self.print_summary()

    def print_summary(self):
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        print("\n\n" + "📊 LOAD TEST RESOURCE SUMMARY")
        print("=" * 50)
        print(f"Duration: {duration:.1f} seconds")
        print("-" * 50)
        
        for name, data in [("API (Uvicorn)", self.stats["api"]), ("Worker (Arq)", self.stats["worker"])]:
            if data["cpu"]:
                avg_cpu = sum(data["cpu"]) / len(data["cpu"])
                max_cpu = max(data["cpu"])
                avg_mem = sum(data["memory"]) / len(data["memory"])
                max_mem = max(data["memory"])
                
                print(f"🔹 {name}:")
                print(f"   CPU (Avg/Max): {avg_cpu:.1f}% / {max_cpu:.1f}%")
                print(f"   RAM (Avg/Max): {avg_mem:.1f} MB / {max_mem:.1f} MB")
            else:
                print(f"❌ {name}: No data found (process not running?)")
                
        if self.stats["system"]["cpu"]:
             print(f"🔹 Global System CPU Max: {max(self.stats['system']['cpu']):.1f}%")
        
        print("=" * 50 + "\n")

if __name__ == "__main__":
    monitor = ResourceMonitor(interval=2)
    monitor.run()

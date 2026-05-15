#!/usr/bin/env python3
"""
Open WebUI Docker Manager - Production Ready (2026)
CustomTkinter + Docker SDK
Readiness, health checks, and beginner-friendly UX improvements
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import docker
from docker import errors as docker_errors
from docker.types import DeviceRequest
import threading
import queue
import json
import os
import webbrowser
import platform
import subprocess
import re
import socket
import urllib.request
from pathlib import Path
from datetime import datetime
import yaml
import time


class OpenWebUIDockerManager(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Open WebUI Docker Manager • 2026")
        self.geometry("1100x820")
        self.minsize(1000, 740)

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # === State ===
        self.container_name_var = ctk.StringVar(value="open-webui")
        self.port_var = ctk.StringVar(value="3000")
        self.volume_var = ctk.StringVar(value="open-webui")
        self.ollama_volume_var = ctk.StringVar(value="ollama")
        self.image_var = ctk.StringVar(value="ghcr.io/open-webui/open-webui:main")
        self.auth_var = ctk.BooleanVar(value=True)
        self.add_host_var = ctk.BooleanVar(value=True)
        self.ollama_url_var = ctk.StringVar(value="http://host.docker.internal:11434")
        self.host_ip_var = ctk.StringVar(value="")
        self.gpu_var = ctk.BooleanVar(value=False)
        self.restart_policy_var = ctk.StringVar(value="unless-stopped")
        self.use_compose_var = ctk.BooleanVar(value=False)

        self.docker_client = None
        self.log_queue = queue.Queue()
        self.following_logs = False
        self.log_thread = None
        self.current_container = None
        self.deploy_cancelled = False
        self.auto_refresh_enabled = False
        self.status_poll_job = None
        self.system = platform.system()

        self._create_ui()
        self.load_config()
        self.check_docker_status()
        self._start_status_polling()

    # ==================== UI ====================
    def _create_ui(self):
        header = ctk.CTkFrame(self, height=70, corner_radius=0, fg_color=("#1a1a1a", "#121212"))
        header.pack(fill="x", padx=0, pady=0)

        ctk.CTkLabel(header, text="🦙 Open WebUI Docker Manager",
                     font=ctk.CTkFont(size=24, weight="bold")).pack(side="left", padx=25, pady=18)

        self.docker_status_label = ctk.CTkLabel(header, text="Docker: Checking...", font=ctk.CTkFont(size=13))
        self.docker_status_label.pack(side="right", padx=15)

        ctk.CTkButton(header, text="🔄 Check Docker", width=130, height=32,
                      command=self.check_docker_status, fg_color="#3a3a3a").pack(side="right", padx=8)

        self.tabview = ctk.CTkTabview(self, width=1060, height=700, corner_radius=12)
        self.tabview.pack(padx=12, pady=(8, 4), fill="both", expand=True)

        self.deploy_tab = self.tabview.add("🚀 Deploy")
        self.manage_tab = self.tabview.add("📦 Manage")
        self.logs_tab = self.tabview.add("📜 Logs")
        self.help_tab = self.tabview.add("❓ Help")

        self._create_deploy_tab()
        self._create_manage_tab()
        self._create_logs_tab()
        self._create_help_tab()

        self.status_bar = ctk.CTkLabel(self, text="Ready — Select the Standard preset to use CPU mode (recommended)",
                                       anchor="w", height=28, font=ctk.CTkFont(size=11))
        self.status_bar.pack(fill="x", padx=12, pady=(0, 8))

    def _create_deploy_tab(self):
        # Presets
        preset_frame = ctk.CTkFrame(self.deploy_tab, corner_radius=10)
        preset_frame.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkLabel(preset_frame, text="Quick Presets (GPU is optional)",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(10, 6))

        btn_frame = ctk.CTkFrame(preset_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        presets = [
            ("Standard\n(CPU - Recommended)", self.apply_standard_preset),
            ("NVIDIA GPU\n(CUDA)", self.apply_nvidia_preset),
            ("Bundled Ollama\n(CPU)", self.apply_bundled_preset),
            ("Custom / Advanced", self.apply_custom_preset),
        ]
        for i, (text, cmd) in enumerate(presets):
            btn = ctk.CTkButton(btn_frame, text=text, command=cmd, width=170, height=52,
                                font=ctk.CTkFont(size=12, weight="bold"))
            btn.grid(row=0, column=i, padx=5, pady=4, sticky="ew")
            btn_frame.grid_columnconfigure(i, weight=1)

        # Config
        config_outer = ctk.CTkFrame(self.deploy_tab, corner_radius=10)
        config_outer.pack(fill="both", expand=True, padx=12, pady=6)

        left = ctk.CTkFrame(config_outer, corner_radius=8)
        left.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)

        ctk.CTkLabel(left, text="Basic Configuration", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=12, pady=(8, 4))

        self._add_labeled_entry(left, "Container Name", self.container_name_var)
        self._add_labeled_entry(left, "Host Port", self.port_var)
        self._add_labeled_entry(left, "WebUI Volume", self.volume_var)
        self._add_labeled_entry(left, "Ollama Volume (when using :ollama)", self.ollama_volume_var)
        self._add_labeled_entry(left, "Docker Image", self.image_var)

        ctk.CTkCheckBox(left, text="Enable Authentication (WEBUI_AUTH=true)", variable=self.auth_var,
                        font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12, pady=6)

        gpu_cb = ctk.CTkCheckBox(left, text="Enable NVIDIA GPU Support (--gpus all) [Optional]",
                                 variable=self.gpu_var, command=self._on_gpu_toggle, font=ctk.CTkFont(size=12))
        gpu_cb.pack(anchor="w", padx=12, pady=2)
        ctk.CTkLabel(left, text="⚠️ Only needed if you have an NVIDIA GPU + NVIDIA Container Toolkit",
                     font=ctk.CTkFont(size=10), text_color="#888888").pack(anchor="w", padx=12, pady=(0, 6))

        right = ctk.CTkFrame(config_outer, corner_radius=8)
        right.pack(side="right", fill="both", expand=True, padx=(4, 8), pady=8)

        ctk.CTkLabel(right, text="Ollama Connection & Advanced", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=12, pady=(8, 4))

        ctk.CTkCheckBox(right, text="Add host.docker.internal:host-gateway", variable=self.add_host_var,
                        font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12, pady=2)

        self._add_labeled_entry(right, "OLLAMA_BASE_URL (leave empty = bundled)", self.ollama_url_var)

        if self.system == "Linux":
            ctk.CTkLabel(right, text="Linux: Host IP (if host.docker.internal fails)",
                         font=ctk.CTkFont(size=11, weight="bold"), text_color="#f59e0b").pack(anchor="w", padx=12, pady=(8, 2))
            self._add_labeled_entry(right, "", self.host_ip_var)
            ctk.CTkButton(right, text="🔍 Detect Host IP", command=self._detect_host_ip,
                          width=180, height=28, fg_color="#854d0e").pack(anchor="w", padx=12, pady=2)

        ctk.CTkLabel(right, text="Restart Policy", font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", padx=12, pady=(8, 2))
        ctk.CTkComboBox(right, values=["no", "on-failure", "always", "unless-stopped"],
                        variable=self.restart_policy_var, width=200, height=28).pack(anchor="w", padx=12, pady=2)

        ctk.CTkCheckBox(right, text="Use Docker Compose (recommended for production)",
                        variable=self.use_compose_var, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12, pady=(10, 2))

        ctk.CTkLabel(right, text="Extra Env Vars (KEY=VALUE per line)",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=12, pady=(6, 2))
        self.extra_env_text = ctk.CTkTextbox(right, height=80, font=ctk.CTkFont(size=10))
        self.extra_env_text.pack(fill="x", padx=12, pady=(0, 8))
        self.extra_env_text.insert("1.0", "# Example:\n# OLLAMA_KEEP_ALIVE=5m\n")

        # Action buttons
        action_frame = ctk.CTkFrame(self.deploy_tab, fg_color="transparent")
        action_frame.pack(fill="x", padx=12, pady=(4, 8))

        ctk.CTkButton(action_frame, text="📋 Show Docker Run / Compose Command", command=self.show_docker_command,
                      width=260, height=36, fg_color="#424242").pack(side="left", padx=4)

        self.deploy_btn = ctk.CTkButton(action_frame, text="🚀 Deploy / Redeploy", command=self.start_deploy_thread,
                                        width=260, height=42, font=ctk.CTkFont(size=14, weight="bold"),
                                        fg_color="#166534", hover_color="#14532d")
        self.deploy_btn.pack(side="right", padx=4)

        # Progress
        self.progress_frame = ctk.CTkFrame(self.deploy_tab, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=12, pady=(0, 4))
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="", font=ctk.CTkFont(size=10))
        self.progress_label.pack(anchor="w")
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, width=600, height=16, mode="determinate")
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=2)
        self.progress_frame.pack_forget()

    def _add_labeled_entry(self, parent, label, var):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=3)
        if label:
            ctk.CTkLabel(row, text=label, width=220, anchor="w", font=ctk.CTkFont(size=11)).pack(side="left")
        entry = ctk.CTkEntry(row, textvariable=var, width=260, height=28)
        entry.pack(side="left", fill="x", expand=True, padx=(5, 0))

    def _on_gpu_toggle(self):
        if self.gpu_var.get():
            if messagebox.askyesno("Enable GPU", "Do you have an NVIDIA GPU + NVIDIA Container Toolkit installed?"):
                self.image_var.set("ghcr.io/open-webui/open-webui:cuda")
            else:
                self.gpu_var.set(False)
        else:
            if "cuda" in self.image_var.get().lower():
                self.image_var.set("ghcr.io/open-webui/open-webui:main")

    # ==================== PRESETS ====================
    def apply_standard_preset(self):
        self.image_var.set("ghcr.io/open-webui/open-webui:main")
        self.add_host_var.set(True)
        self.ollama_url_var.set("http://host.docker.internal:11434")
        self.gpu_var.set(False)
        self.auth_var.set(True)
        self.restart_policy_var.set("unless-stopped")
        self.use_compose_var.set(False)
        self.update_status_bar("✅ Standard preset (CPU) — No GPU required")

    def apply_nvidia_preset(self):
        self.image_var.set("ghcr.io/open-webui/open-webui:cuda")
        self.add_host_var.set(True)
        self.ollama_url_var.set("http://host.docker.internal:11434")
        self.gpu_var.set(True)
        self.auth_var.set(True)
        self.restart_policy_var.set("unless-stopped")
        self.use_compose_var.set(False)
        self.update_status_bar("✅ NVIDIA preset — Uses GPU acceleration")

    def apply_bundled_preset(self):
        self.image_var.set("ghcr.io/open-webui/open-webui:ollama")
        self.add_host_var.set(False)
        self.ollama_url_var.set("")
        self.gpu_var.set(False)
        self.auth_var.set(True)
        self.restart_policy_var.set("unless-stopped")
        self.use_compose_var.set(True)
        self.update_status_bar("✅ Bundled Ollama (CPU)")

    def apply_custom_preset(self):
        self.update_status_bar("✏️ Custom mode")

    # ==================== POLLING ====================
    def _start_status_polling(self):
        self.auto_refresh_enabled = True
        self._poll_container_status()

    def _poll_container_status(self):
        if not self.winfo_exists() or not getattr(self, "auto_refresh_enabled", False):
            return
        try:
            if self.tabview.get() == "📦 Manage":
                self.update_manage_status()
        except Exception:
            pass
        self.status_poll_job = self.after(5000, self._poll_container_status)

    # ==================== HELPERS ====================
    def _is_port_available(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return True
            except OSError:
                return False

    def validate_before_deploy(self):
        try:
            port = int(self.port_var.get().strip())
            if not (1 <= port <= 65535):
                raise ValueError()
        except:
            messagebox.showerror("Error", "Port must be a number from 1 to 65535")
            return False

        if not self._is_port_available(port):
            if not messagebox.askyesno("Port Warning", f"Port {port} is already in use.\nDo you want to continue?"):
                return False

        name = self.container_name_var.get().strip()
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]+$", name):
            messagebox.showerror("Error", "Invalid container name")
            return False
        return True

    def _detect_host_ip(self):
        try:
            if self.system == "Linux":
                out = subprocess.check_output("ip route get 1 | awk '{print $7; exit}'", shell=True, text=True).strip()
                if not out:
                    out = subprocess.check_output("hostname -I | awk '{print $1}'", shell=True, text=True).strip()
                if out:
                    self.host_ip_var.set(out)
                    messagebox.showinfo("Detected", f"Host IP: {out}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== DEPLOY ====================
    def start_deploy_thread(self):
        if not self.validate_before_deploy():
            return
        self.deploy_cancelled = False
        self.deploy_btn.configure(state="disabled", text="⏳ Deploying...")
        self.progress_frame.pack(fill="x", padx=12, pady=(0, 4))
        self.progress_bar.set(0)
        threading.Thread(target=self._deploy_worker, daemon=True).start()

    def _deploy_worker(self):
        try:
            client = self.get_docker_client()
            if not client:
                return

            image = self.image_var.get().strip()
            name = self.container_name_var.get().strip()
            port = int(self.port_var.get().strip())
            webui_vol = self.volume_var.get().strip()
            ollama_vol = self.ollama_volume_var.get().strip() or "ollama"
            use_compose = self.use_compose_var.get()
            is_bundled = "ollama" in image.lower()

            # Create volumes
            for v in [webui_vol, ollama_vol if is_bundled else None]:
                if v:
                    try:
                        client.volumes.get(v)
                    except docker_errors.NotFound:
                        client.volumes.create(name=v)

            self._pull_image_with_progress(client, image)
            if self.deploy_cancelled:
                return

            if use_compose:
                self._deploy_with_compose(client, image, name, port, webui_vol, ollama_vol, is_bundled)
            else:
                self._deploy_with_run(client, image, name, port, webui_vol, ollama_vol, is_bundled)

            self.save_config()
            self.after(0, self._on_deploy_success)
        except docker_errors.APIError as e:
            if "port is already allocated" in str(e).lower():
                self.show_error(f"Port {port} is already in use.\n\nChange the port or stop the container currently using it.")
            else:
                self.show_error(f"Docker API Error:\n{str(e)}")
        except Exception as e:
            self.show_error(f"Deployment failed:\n{str(e)}")
        finally:
            self.after(0, lambda: self.deploy_btn.configure(state="normal", text="🚀 Deploy / Redeploy"))
            self.after(0, lambda: self.progress_frame.pack_forget())

    def _pull_image_with_progress(self, client, image):
        try:
            client.images.get(image)
            self.after(0, lambda: self.progress_bar.set(1.0))
            return
        except docker_errors.ImageNotFound:
            pass

        resp = client.api.pull(image, stream=True, decode=True)
        for line in resp:
            if self.deploy_cancelled:
                break
            status = line.get("status", "")
            if status:
                self.after(0, lambda s=status: self.update_status_bar(s[:80]))

    def _deploy_with_run(self, client, image, name, port, webui_vol, ollama_vol, is_bundled):
        try:
            old = client.containers.get(name)
            if old.status == "running":
                old.stop(timeout=15)
            old.remove()
        except docker_errors.NotFound:
            pass

        volumes = {webui_vol: {"bind": "/app/backend/data", "mode": "rw"}}
        if is_bundled:
            volumes[ollama_vol] = {"bind": "/root/.ollama", "mode": "rw"}

        env = {"WEBUI_AUTH": str(self.auth_var.get()).lower()}
        if self.ollama_url_var.get().strip():
            env["OLLAMA_BASE_URL"] = self.ollama_url_var.get().strip()

        for line in self.extra_env_text.get("1.0", tk.END).splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

        extra_hosts = None
        if self.add_host_var.get():
            if self.system == "Linux" and self.host_ip_var.get().strip():
                extra_hosts = {"host.docker.internal": self.host_ip_var.get().strip()}
            else:
                extra_hosts = {"host.docker.internal": "host-gateway"}

        device_requests = None
        if self.gpu_var.get():
            device_requests = [DeviceRequest(count=-1, capabilities=[["gpu"]])]

        # === CREATE CONTAINER ===
        container = client.containers.run(
            image=image,
            name=name,
            detach=True,
            ports={"8080/tcp": ("0.0.0.0", port)},   # Explicitly bind to 0.0.0.0
            volumes=volumes,
            environment=env,
            extra_hosts=extra_hosts,
            device_requests=device_requests,
            restart_policy={"Name": self.restart_policy_var.get()}
        )

        # === CHECK IMMEDIATELY AFTER CREATION (catch early crashes) ===
        time.sleep(2.5)
        container.reload()
        if container.status != "running":
            logs = container.logs(tail=60).decode("utf-8", errors="replace")
            raise Exception(
                f"Container was created but could NOT start!\n\n"
                f"Status: {container.status}\n\n"
                f"Recent logs:\n{logs}\n\n"
                f"→ Open the '📜 Logs' tab for details or run: docker logs {name}"
            )

    def _deploy_with_compose(self, client, image, name, port, webui_vol, ollama_vol, is_bundled):
        compose_dir = Path.home() / ".open-webui-manager"
        compose_dir.mkdir(parents=True, exist_ok=True)
        compose_file = compose_dir / f"docker-compose-{name}.yml"

        compose_dict = {
            "services": {
                name: {
                    "image": image,
                    "container_name": name,
                    "ports": [f"{port}:8080"],
                    "volumes": [f"{webui_vol}:/app/backend/data"],
                    "restart": self.restart_policy_var.get(),
                    "environment": {
                        "WEBUI_AUTH": str(self.auth_var.get()).lower()
                    }
                }
            }
        }

        if is_bundled:
            compose_dict["services"][name]["volumes"].append(f"{ollama_vol}:/root/.ollama")

        if self.ollama_url_var.get().strip():
            compose_dict["services"][name]["environment"]["OLLAMA_BASE_URL"] = self.ollama_url_var.get().strip()

        if self.add_host_var.get():
            host = self.host_ip_var.get().strip() if (self.system == "Linux" and self.host_ip_var.get().strip()) else "host-gateway"
            compose_dict["services"][name]["extra_hosts"] = [f"host.docker.internal:{host}"]

        if self.gpu_var.get():
            compose_dict["services"][name]["deploy"] = {
                "resources": {
                    "reservations": {
                        "devices": [{
                            "driver": "nvidia",
                            "count": "all",
                            "capabilities": ["gpu"]
                        }]
                    }
                }
            }

        with open(compose_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(compose_dict, f, sort_keys=False, default_flow_style=False)

        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "up", "-d", "--remove-orphans"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise Exception(result.stderr or result.stdout)

    def _on_deploy_success(self):
        self.update_manage_status()
        self.tabview.set("📦 Manage")

        port = self.port_var.get().strip()
        name = self.container_name_var.get().strip()

        client = self.get_docker_client()
        if client:
            try:
                container = client.containers.get(name)
                if container.status != "running":
                    messagebox.showwarning(
                        "Warning",
                        f"The container was created but its current status is: {container.status.upper()}\n\n"
                        "Open the '📜 Logs' tab to inspect the error details."
                    )
                    return
            except:
                pass

        messagebox.showinfo(
            "Deployment Successful",
            f"✅ The container was created and started.\n\n"
            f"⚠️ FIRST START CAN TAKE 25–60 SECONDS (sometimes longer)\n"
            f"   because Open WebUI is running Alembic migrations and initializing the database.\n\n"
            f"URL: http://localhost:{port}\n\n"
            f"The app will automatically check and notify you when it is ready."
        )

        # Start readiness polling
        self.after(4000, lambda: self._check_webui_ready(port, attempt=1))

    # ==================== READINESS CHECK (NEW - IMPORTANT) ====================
    def _check_webui_ready(self, port, attempt=1, max_attempts=18):
        """Strong readiness check: Docker Health + /health endpoint"""
        name = self.container_name_var.get().strip()
        client = self.get_docker_client()

        health_status = "unknown"
        container_running = False

        if client:
            try:
                container = client.containers.get(name)
                container.reload()
                container_running = container.status == "running"
                health_info = container.attrs.get("State", {}).get("Health", {})
                health_status = health_info.get("Status", "unknown")
            except:
                pass

        # Prefer the official /health endpoint
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/health", method="GET")
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    self.update_status_bar(f"✅ WebUI is ready at http://localhost:{port}")
                    return
        except:
            pass

        # Update status
        if container_running:
            if health_status == "healthy":
                self.update_status_bar(f"✅ WebUI is healthy → try opening it in your browser")
                return
            elif health_status == "starting":
                self.update_status_bar(f"⏳ WebUI is starting up (Health: starting) - Attempt {attempt}/{max_attempts}")
            else:
                self.update_status_bar(f"⏳ Waiting for WebUI to become ready... (Attempt {attempt}/{max_attempts})")
        else:
            self.update_status_bar(f"❌ Container stopped. Check the Logs tab now!")
            return

        if attempt < max_attempts:
            self.after(4000, lambda: self._check_webui_ready(port, attempt + 1, max_attempts))
        else:
            self.update_status_bar(f"⚠️ Still not ready after ~70s. Check the Manage/Logs tabs.")

    def check_webui_connection(self):
        """Button handler for checking WebUI connectivity."""
        import urllib.request
        port = self.port_var.get().strip()
        url = f"http://127.0.0.1:{port}"

        client = self.get_docker_client()
        if client:
            try:
                container = client.containers.get(self.container_name_var.get().strip())
                container.reload()
                if container.status != "running":
                    messagebox.showwarning("Warning", "The container is not running. Start it first.")
                    return
                health = container.attrs.get("State", {}).get("Health", {}).get("Status", "")
                if health:
                    messagebox.showinfo("Docker Health", f"Health status: {health}")
            except:
                pass

        try:
            req = urllib.request.Request(f"{url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    messagebox.showinfo("Success", f"WebUI is ready!\n{url}\nHTTP 200 + /health OK")
                    webbrowser.open(url)
                    return
        except Exception as e:
            messagebox.showerror("Connection Failed",
                f"Could not connect {url}\n\nError: {str(e)}\n\n"
                f"→ Check:\n"
                f"  • Is the container running? (Manage tab)\n"
                f"  • Is the health status 'healthy'?\n"
                f"  • Wait another 20-40 seconds (first start takes longer)\n"
                f"  • Check the '📜 Logs' tab for details")

    # ==================== DOCKER ====================
    def get_docker_client(self):
        if self.docker_client is None:
            try:
                self.docker_client = docker.from_env()
                self.docker_client.ping()
            except Exception as e:
                self.docker_client = None
                self.show_error(f"Connection Failed Docker:\n{e}\n\n"
                                "• Windows/macOS: Open Docker Desktop\n"
                                "• Linux: Check docker group permissions or start Docker")
                return None
        return self.docker_client

    def check_docker_status(self):
        try:
            client = docker.from_env()
            client.ping()
            ver = client.version().get("Version", "unknown")
            self.docker_status_label.configure(text=f"✅ Docker {ver}", text_color="#4ade80")
            self.docker_client = client
        except Exception as e:
            self.docker_status_label.configure(text="❌ Docker unavailable", text_color="#f87171")
            self.docker_client = None
            if "permission denied" in str(e).lower():
                messagebox.showwarning("Permission Error",
                    "Linux: Run the following command, then log out and back in:\n"
                    "sudo usermod -aG docker $USER")

    def update_status_bar(self, text):
        self.status_bar.configure(text=text)

    def show_error(self, msg):
        self.after(0, lambda: messagebox.showerror("Error", msg))

    def show_docker_command(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Equivalent Docker Commands")
        popup.geometry("980x720")
        popup.grab_set()
        popup.transient(self)
        popup.focus_set()

        name = self.container_name_var.get().strip()
        port = self.port_var.get().strip()
        img = self.image_var.get().strip()
        webui_vol = self.volume_var.get().strip()
        ollama_vol = self.ollama_volume_var.get().strip() or "ollama"
        is_bundled = "ollama" in img.lower()

        run_cmd = f"""docker run -d \\
  --name {name} \\
  -p {port}:8080 \\
  -v {webui_vol}:/app/backend/data \\"""

        if is_bundled:
            run_cmd += f"\n  -v {ollama_vol}:/root/.ollama \\"

        if self.gpu_var.get():
            run_cmd += "\n  --gpus all \\"

        if self.add_host_var.get():
            host = self.host_ip_var.get().strip() if (self.system == "Linux" and self.host_ip_var.get().strip()) else "host-gateway"
            run_cmd += f"\n  --add-host=host.docker.internal:{host} \\"

        run_cmd += f"\n  --restart {self.restart_policy_var.get()} \\"

        env_lines = [f'  -e WEBUI_AUTH={str(self.auth_var.get()).lower()}']
        if self.ollama_url_var.get().strip():
            env_lines.append(f'  -e OLLAMA_BASE_URL={self.ollama_url_var.get().strip()}')

        for line in self.extra_env_text.get("1.0", tk.END).splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                env_lines.append(f"  -e {line}")

        run_cmd += "\n" + "\n".join(env_lines)
        run_cmd += f"\n  {img}"

        ctk.CTkLabel(popup, text="Docker Run Command (full):", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))
        run_text = ctk.CTkTextbox(popup, height=220, font=ctk.CTkFont(family="Consolas", size=11))
        run_text.pack(fill="x", padx=20, pady=5)
        run_text.insert("1.0", run_cmd)
        run_text.configure(state="disabled")

        ctk.CTkButton(popup, text="📋 Copy Docker Run", command=lambda: self._copy_to_clipboard(run_cmd)).pack(pady=5)

        ctk.CTkLabel(popup, text="Docker Compose (equivalent):", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))
        compose_text = ctk.CTkTextbox(popup, height=200, font=ctk.CTkFont(family="Consolas", size=11))
        compose_text.pack(fill="x", padx=20, pady=5)

        compose_dict = {
            "services": {
                name: {
                    "image": img,
                    "container_name": name,
                    "ports": [f"{port}:8080"],
                    "volumes": [f"{webui_vol}:/app/backend/data"],
                    "restart": self.restart_policy_var.get(),
                    "environment": {"WEBUI_AUTH": str(self.auth_var.get()).lower()}
                }
            }
        }
        if is_bundled:
            compose_dict["services"][name]["volumes"].append(f"{ollama_vol}:/root/.ollama")
        if self.ollama_url_var.get().strip():
            compose_dict["services"][name]["environment"]["OLLAMA_BASE_URL"] = self.ollama_url_var.get().strip()
        if self.add_host_var.get():
            host = self.host_ip_var.get().strip() if (self.system == "Linux" and self.host_ip_var.get().strip()) else "host-gateway"
            compose_dict["services"][name]["extra_hosts"] = [f"host.docker.internal:{host}"]
        if self.gpu_var.get():
            compose_dict["services"][name]["deploy"] = {
                "resources": {"reservations": {"devices": [{"driver": "nvidia", "count": "all", "capabilities": ["gpu"]}]}}
            }

        compose_text.insert("1.0", yaml.safe_dump(compose_dict, sort_keys=False))
        compose_text.configure(state="disabled")

        ctk.CTkButton(popup, text="📋 Copy Compose YAML", command=lambda: self._copy_to_clipboard(yaml.safe_dump(compose_dict))).pack(pady=5)

    def _copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "Copied to clipboard!")

    # ==================== CONFIG ====================
    def save_config(self):
        try:
            cfg = {
                "version": 1,
                "container_name": self.container_name_var.get(),
                "host_port": self.port_var.get(),
                "volume_name": self.volume_var.get(),
                "image": self.image_var.get(),
                "gpu_enabled": self.gpu_var.get(),
                "auth_enabled": self.auth_var.get(),
                "add_host": self.add_host_var.get(),
                "ollama_url": self.ollama_url_var.get(),
                "restart_policy": self.restart_policy_var.get(),
                "use_compose": self.use_compose_var.get(),
                "extra_env": self.extra_env_text.get("1.0", tk.END),
            }
            p = Path.home() / ".open-webui-manager"
            p.mkdir(parents=True, exist_ok=True)
            with open(p / "config.json", "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except:
            pass

    def load_config(self):
        try:
            f = Path.home() / ".open-webui-manager" / "config.json"
            if f.exists():
                with open(f, "r", encoding="utf-8") as fh:
                    cfg = json.load(fh)
                self.container_name_var.set(cfg.get("container_name", "open-webui"))
                self.port_var.set(cfg.get("host_port", "3000"))
                self.volume_var.set(cfg.get("volume_name", "open-webui"))
                self.image_var.set(cfg.get("image", "ghcr.io/open-webui/open-webui:main"))
                self.gpu_var.set(cfg.get("gpu_enabled", False))
                self.auth_var.set(cfg.get("auth_enabled", True))
                self.add_host_var.set(cfg.get("add_host", True))
                self.ollama_url_var.set(cfg.get("ollama_url", "http://host.docker.internal:11434"))
                self.restart_policy_var.set(cfg.get("restart_policy", "unless-stopped"))
                self.use_compose_var.set(cfg.get("use_compose", False))
                extra = cfg.get("extra_env", "")
                if extra:
                    self.extra_env_text.delete("1.0", tk.END)
                    self.extra_env_text.insert("1.0", extra)
        except:
            pass

    # ==================== MANAGE ====================
    def _create_manage_tab(self):
        frame = ctk.CTkFrame(self.manage_tab, corner_radius=10)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        self.manage_status_label = ctk.CTkLabel(frame, text="Status: Not checked yet",
                                                font=ctk.CTkFont(size=16, weight="bold"))
        self.manage_status_label.pack(pady=20)

        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(pady=10)

        ctk.CTkButton(btn_frame, text="🔄 Refresh", command=self.update_manage_status, width=120).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="▶️ Start", command=lambda: self.manage_action("start"), fg_color="#16a34a").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="⏹️ Stop", command=lambda: self.manage_action("stop"), fg_color="#dc2626").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🔁 Restart", command=lambda: self.manage_action("restart")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🗑️ Remove", command=lambda: self.manage_action("remove"), fg_color="#7c3aed").pack(side="left", padx=5)

        ctk.CTkButton(frame, text="🌐 Open WebUI in Browser",
                      command=self.open_in_browser, fg_color="#2563eb", height=40).pack(pady=10)

        # === NEW IMPORTANT BUTTON ===
        ctk.CTkButton(frame, text="🔍 Check WebUI Connection (Health + /health)",
                      command=self.check_webui_connection,
                      fg_color="#0e7490", height=36).pack(pady=8)

    def update_manage_status(self):
        client = self.get_docker_client()
        if not client:
            return
        name = self.container_name_var.get().strip()
        try:
            container = client.containers.get(name)
            self.current_container = container
            status = container.status.upper()

            health = container.attrs.get("State", {}).get("Health", {}).get("Status", "")
            health_text = f" | Health: {health}" if health else ""

            ports_info = container.attrs.get("NetworkSettings", {}).get("Ports", {})
            host_port = None
            if ports_info:
                for cp, bindings in ports_info.items():
                    if bindings:
                        host_port = bindings[0].get("HostPort")
                        break

            if status == "RUNNING":
                color = "#4ade80"
                text = f"✅ {name} — RUNNING{health_text}"
            elif status == "EXITED":
                color = "#ef4444"
                text = f"❌ {name} — STOPPED (Exited){health_text}"
            else:
                color = "#fbbf24"
                text = f"⚠️ {name} — {status}{health_text}"

            if host_port:
                text += f"  |  Port: {host_port}"

            self.manage_status_label.configure(text=text, text_color=color)
        except docker_errors.NotFound:
            self.manage_status_label.configure(text=f"❓ Container '{name}' has not been created", text_color="#9ca3af")

    def manage_action(self, action):
        client = self.get_docker_client()
        if not client:
            return
        name = self.container_name_var.get().strip()
        try:
            container = client.containers.get(name)
        except docker_errors.NotFound:
            messagebox.showwarning("Not Found", "The container does not exist yet. Deploy it first.")
            return

        if action == "start":
            container.start()
        elif action == "stop":
            container.stop(timeout=20)
        elif action == "restart":
            container.restart(timeout=20)
        elif action == "remove":
            if messagebox.askyesno("Confirm", f"Remove container {name}?"):
                if container.status == "running":
                    container.stop(timeout=15)
                container.remove()
                self.current_container = None

        self.update_manage_status()

    def open_in_browser(self):
        client = self.get_docker_client()
        if not client:
            return
        try:
            container = client.containers.get(self.container_name_var.get().strip())
            if container.status != "running":
                messagebox.showwarning("Warning", "The container is not running. Start it first.")
                return
        except:
            messagebox.showwarning("Warning", "Container not found.")
            return
        webbrowser.open(f"http://localhost:{self.port_var.get()}")

    # ==================== LOGS ====================
    def _create_logs_tab(self):
        frame = ctk.CTkFrame(self.logs_tab, corner_radius=10)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        self.logs_text = ctk.CTkTextbox(frame, height=450, font=ctk.CTkFont(family="Consolas", size=10))
        self.logs_text.pack(fill="both", expand=True, padx=8, pady=6)

        ctrl = ctk.CTkFrame(frame)
        ctrl.pack(fill="x", pady=4)

        ctk.CTkButton(ctrl, text="📥 Load Last 200 Lines", command=self.load_recent_logs).pack(side="left", padx=5)
        self.follow_btn = ctk.CTkButton(ctrl, text="▶️ Follow Live Logs", command=self.toggle_follow_logs, fg_color="#0288d1")
        self.follow_btn.pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="Clear", command=self.clear_logs).pack(side="left", padx=5)

    def load_recent_logs(self):
        client = self.get_docker_client()
        if not client:
            return
        try:
            container = client.containers.get(self.container_name_var.get().strip())
            logs = container.logs(tail=200, timestamps=True).decode("utf-8", errors="replace")
            self.logs_text.delete("1.0", tk.END)
            self.logs_text.insert("1.0", logs)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def toggle_follow_logs(self):
        if self.following_logs:
            self.following_logs = False
            self.follow_btn.configure(text="▶️ Follow Live Logs", fg_color="#0288d1")
        else:
            self.following_logs = True
            self.follow_btn.configure(text="⏹️ Stop Following", fg_color="#b91c1c")

            if self.log_thread and self.log_thread.is_alive():
                self.following_logs = False

            self.log_thread = threading.Thread(target=self._follow_logs_worker, daemon=True)
            self.log_thread.start()
            self.after(150, self._drain_log_queue_periodic)

    def _follow_logs_worker(self):
        client = self.get_docker_client()
        if not client:
            return
        try:
            container = client.containers.get(self.container_name_var.get().strip())
            self.after(0, lambda: self.logs_text.delete("1.0", "end"))
            for line in container.logs(stream=True, follow=True, timestamps=True):
                if not self.following_logs:
                    break
                try:
                    decoded = line.decode("utf-8", errors="replace")
                    self.log_queue.put(decoded)
                except:
                    pass
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error Logs", str(e)))
        finally:
            self.following_logs = False
            self.after(0, lambda: self.follow_btn.configure(text="▶️ Follow Live Logs", fg_color="#0288d1"))

    def _drain_log_queue_periodic(self):
        if not self.following_logs or not self.winfo_exists():
            return
        try:
            while not self.log_queue.empty():
                line = self.log_queue.get_nowait()
                self.logs_text.insert("end", line)
                self.logs_text.see("end")
        except:
            pass
        if self.following_logs:
            self.after(150, self._drain_log_queue_periodic)

    def clear_logs(self):
        self.logs_text.delete("1.0", tk.END)

    # ==================== HELP ====================
    def _create_help_tab(self):
        frame = ctk.CTkFrame(self.help_tab, corner_radius=10)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        text = ctk.CTkTextbox(frame, font=ctk.CTkFont(size=12))
        text.pack(fill="both", expand=True, padx=15, pady=10)

        help_content = """Quick Guide (UPDATED):

1. Select the "Standard (CPU)" preset if you do not need GPU support.
2. GPU support is only needed when you have an NVIDIA GPU + NVIDIA Container Toolkit.
3. Enable Docker Compose if you want a production-style deployment.
4. FIRST DEPLOY: WAIT 25–60 SECONDS before opening the browser (migrations + database initialization).
5. After deployment, use "🔍 Check WebUI Connection" to verify readiness.
6. If the container exited, open the Logs tab immediately to inspect the error.
7. Data is stored in Docker volumes, so removing the container does not delete app data.
8. Follow Live Logs uses periodic draining to avoid UI lag.
"""
        text.insert("1.0", help_content)
        text.configure(state="disabled")

    def on_closing(self):
        self.auto_refresh_enabled = False
        self.following_logs = False

        if getattr(self, "status_poll_job", None):
            try:
                self.after_cancel(self.status_poll_job)
            except:
                pass

        self.save_config()
        self.destroy()


if __name__ == "__main__":
    app = OpenWebUIDockerManager()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

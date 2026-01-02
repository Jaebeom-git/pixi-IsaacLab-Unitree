# pixi-IsaacLab-unitreeG1

A reproducible Pixi environment for **IsaacLab / Isaac Sim** and **Unitree RL Lab (G1)** workflows.

This repository tracks the **environment definition** (Pixi manifest + lockfile) and **setup scripts** only.
Large binaries, cloned repos, caches, and experiment outputs are intentionally ignored.

---

## Requirements

- OS: Ubuntu 22.04
- `git`
- `pixi` installed  ([Installation guide](https://pixi.prefix.dev/latest/installation/))


GPU drivers / CUDA runtime should be installed according to your machine.

---

## Quick Start

### 1) Install the Pixi environment

```bash
pixi install
```

#### Offline / Local Wheels via wheelhouse/
If you want to reduce downloads (or install in a limited-network environment), you can provide
pre-downloaded Python wheels in a local wheelhouse/ directory and enable find-links in pixi.toml.

In pixi.toml:
```toml
[pypi-options]
# Uncomment to use local wheels from ./wheelhouse
# find-links = [{ path = "./wheelhouse" }]
```

### 2) IsaacLab setup
```bash
pixi run isaaclab-setup
```

### 3) rsl_rl setup
```bash
pixi rsl-rl-setup
```

### 4) VSCode setup
```bash
pixi run vscode-setup
```

### 5) Unitree setup (clone + patch + editable install)
```bash
pixi run unitree-setup
```



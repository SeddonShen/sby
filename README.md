## 🧩 Integrating Modelchecker with SymbiYosys (SBY)

**[Modelchecker](https://github.com/ISCAS-modelchecker/modelchecker)** can serve as a backend solver in the [SymbiYosys (SBY)](https://github.com/YosysHQ/sby) formal verification flow, enabling fast bit-level checking of Verilog designs, such as modules from [XiangShan](https://github.com/OpenXiangShan/XiangShan).

### ✅ Basic Usage

```bash
python3 /path/to/sby/sbysrc/sby.py /path/to/verify_aig.sby -f --modelchecker /path/to/modelchecker
```

### 📦 Example: Verifying a XiangShan Module
```bash
# Load OSS-CAD Suite environment (adjust the path accordingly)
source /path/to/oss-cad-suite/environment

# Navigate to the target test directory
cd ./sby/benchmark/CoupledL2/CoupledL2_L2AsL1_TileLink_mshrCtl_0508_2L2_L3

# Run SymbiYosys with Modelchecker as the backend solver
python3 ./sby/sbysrc/sby.py ./sby/benchmark/CoupledL2/verify_aig.sby -f --modelchecker ./sby/modelchecker
```
⚠️ Make sure to adjust `/path/to/oss-cad-suite/` to your actual OSS-CAD Suite location.

### ⚙️ Optional: Improve Trace Replay Speed
By default, SBY may use `yices` to replay AIG traces, which can be slow.
To improve performance, change the engine in `sby/sbysrc/sby_mode_bmc.py`:

```python
# Before (line 23):
task.handle_str_option("aigsmt", "yices")
# After:
task.handle_str_option("aigsmt", "bitwuzla")
```

### 🔗 Resources

- 📚 [SymbiYosys Documentation](https://yosyshq.readthedocs.io/projects/sby/)
- 💾 [OSS CAD Suite (Free Download)](https://github.com/YosysHQ/oss-cad-suite-build/releases)
- 🧪 [Tabby CAD Suite (Evaluation License)](https://www.yosyshq.com/tabby-cad-datasheet)
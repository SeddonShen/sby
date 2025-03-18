#
# SymbiYosys (sby) -- Front-end for Yosys-based formal verification flows
#
# Copyright (C) 2016  Claire Xenia Wolf <claire@yosyshq.com>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#

import re, os, getopt, click, json
from sby_core import SbyProc
from sby_sim import sim_witness_trace

def run(mode, task, engine_idx, engine):
    opts, solver_args = getopt.getopt(engine[1:], "", [])

    if len(solver_args) == 0:
        task.error("Missing solver command.")

    for o, a in opts:
        task.error("Unexpected AIGER engine options.")

    status_2 = "UNKNOWN"

    model_variant = ""
    json_output = False

    if solver_args[0] == "suprove":
        if mode not in ["live", "prove"]:
            task.error("The aiger solver 'suprove' is only supported in live and prove modes.")
        if mode == "live" and (len(solver_args) == 1 or solver_args[1][0] != "+"):
            solver_args.insert(1, "+simple_liveness")
        solver_cmd = " ".join([task.exe_paths["suprove"]] + solver_args[1:])

    elif solver_args[0] == "avy":
        model_variant = "_fold"
        if mode != "prove":
            task.error("The aiger solver 'avy' is only supported in prove mode.")
        solver_cmd = " ".join([task.exe_paths["avy"], "--cex", "-"] + solver_args[1:])
    
    elif solver_args[0] == "rIC3":
        if mode != "prove":
            task.error("The aiger solver 'rIC3' is only supported in prove mode.")
        solver_cmd = " ".join([task.exe_paths["rIC3"], "--witness"] + solver_args[1:])

    elif solver_args[0] == "aigbmc":
        if mode != "bmc":
            task.error("The aiger solver 'aigbmc' is only supported in bmc mode.")
        solver_cmd = " ".join([task.exe_paths["aigbmc"], str(task.opt_depth - 1)] + solver_args[1:])
        status_2 = "PASS"  # aigbmc outputs status 2 when BMC passes

    elif solver_args[0] == "modelchecker":
        if mode != "bmc":
            task.error("The aiger solver 'modelchecker' is only supported in BMC mode.")
        print("solver_args:", solver_args[1:])
        solver_cmd = " ".join([task.exe_paths["modelchecker"], "-findbug {}".format(task.opt_depth - 1)] + solver_args[1:])
        status_2 = "PASS"  # modelchecker outputs status 2 when BMC passes

    elif solver_args[0] == "imctk-eqy-engine":
        model_variant = "_fold"
        json_output = True
        if mode != "prove":
            task.error("The aiger solver 'imctk-eqy-engine' is only supported in prove mode.")
        args = ["--bmc-depth", str(task.opt_depth), "--jsonl-output"]
        solver_cmd = " ".join([task.exe_paths["imctk-eqy-engine"], *args, *solver_args[1:]])

    else:
        task.error(f"Invalid solver command {solver_args[0]}.")

    smtbmc_vcd = task.opt_vcd and not task.opt_vcd_sim
    run_aigsmt = (mode != "live") and (smtbmc_vcd or (task.opt_append and task.opt_append_assume))
    smtbmc_append = 0
    sim_append = 0
    log = task.log_prefix(f"engine_{engine_idx}")

    if mode != "live":
        if task.opt_append_assume:
            smtbmc_append = task.opt_append
        elif smtbmc_vcd:
            if not task.opt_append_assume:
                log("For VCDs generated by smtbmc the option 'append_assume off' is ignored")
            smtbmc_append = task.opt_append
        else:
            sim_append = task.opt_append

    proc = SbyProc(
        task,
        f"engine_{engine_idx}",
        task.model(f"aig{model_variant}"),
        f"cd {task.workdir}; {solver_cmd} model/design_aiger{model_variant}.aig",
        logfile=open(f"{task.workdir}/engine_{engine_idx}/logfile.txt", "w")
    )
    if solver_args[0] not in ["avy", "rIC3"]:
        proc.checkretcode = True

    proc_status = None
    produced_cex = False
    end_of_cex = False
    aiw_file = open(f"{task.workdir}/engine_{engine_idx}/trace.aiw", "w")

    def output_callback(line):
        nonlocal proc_status
        nonlocal produced_cex
        nonlocal end_of_cex

        if json_output:
            # Forward log messages, but strip the prefix containing runtime and memory stats
            if not line.startswith('{'):
                print(line, file=proc.logfile, flush=True)
                matched = re.match(r".*(TRACE|DEBUG|INFO|WARN|ERROR) (.*)", line)
                if matched:
                    if matched[1] == "INFO":
                        task.log(matched[2])
                    else:
                        task.log(f"{matched[1]} {matched[2]}")
                return None
            event = json.loads(line)
            if "aiw" in event:
                print(event["aiw"], file=aiw_file)
            if "status" in event:
                if event["status"] == "pass":
                    proc_status = "PASS"
                elif event["status"] == "fail":
                    proc_status = "FAIL"
            return None

        if proc_status is not None:
            if not end_of_cex and not produced_cex and line.isdigit():
                produced_cex = True
            if not end_of_cex:
                print(line, file=aiw_file)
            if line == ".":
                end_of_cex = True
            return None

        if line.startswith("u"):
            return f"No CEX up to depth {int(line[1:])-1}."

        if line in ["0", "1", "2"]:
            print(line, file=aiw_file)
            if line == "0": proc_status = "PASS"
            if line == "1": proc_status = "FAIL"
            if line == "2": proc_status = status_2

        return None

    def exit_callback(retcode):
        aiw_file.close()
        aigsmt_exit_callback(task, engine_idx, proc_status,
            run_aigsmt=run_aigsmt, smtbmc_vcd=smtbmc_vcd, smtbmc_append=smtbmc_append, sim_append=sim_append, )

    proc.output_callback = output_callback
    proc.register_exit_callback(exit_callback)


def aigsmt_exit_callback(task, engine_idx, proc_status, *, run_aigsmt, smtbmc_vcd, smtbmc_append, sim_append):
    if proc_status is None:
        task.error(f"engine_{engine_idx}: Could not determine engine status.")

    task.update_status(proc_status)
    task.summary.set_engine_status(engine_idx, proc_status)
    task.terminate()
    if proc_status == "FAIL" and (not run_aigsmt or task.opt_aigsmt != "none"):
        aigsmt_trace_callback(task, engine_idx, proc_status, run_aigsmt=run_aigsmt, smtbmc_vcd=smtbmc_vcd, smtbmc_append=smtbmc_append, sim_append=sim_append)

def aigsmt_trace_callback(task, engine_idx, proc_status, *, run_aigsmt, smtbmc_vcd, smtbmc_append, sim_append, name="trace"):

    trace_prefix = f"engine_{engine_idx}/{name}"

    aiw2yw_suffix = '_aiw' if run_aigsmt else ''

    witness_proc = SbyProc(
        task, f"engine_{engine_idx}", [],
        f"cd {task.workdir}; {task.exe_paths['witness']} aiw2yw engine_{engine_idx}/{name}.aiw model/design_aiger.ywa engine_{engine_idx}/{name}{aiw2yw_suffix}.yw",
    )
    final_proc = witness_proc

    if run_aigsmt:
        smtbmc_opts = []
        smtbmc_opts += ["-s", task.opt_aigsmt]
        if task.opt_tbtop is not None:
            smtbmc_opts  += ["--vlogtb-top", task.opt_tbtop]
        smtbmc_opts += ["--noprogress", f"--append {smtbmc_append}"]
        if smtbmc_vcd:
            smtbmc_opts += [f"--dump-vcd {trace_prefix}.vcd"]
        smtbmc_opts += [f"--dump-yw {trace_prefix}.yw", f"--dump-vlogtb {trace_prefix}_tb.v", f"--dump-smtc {trace_prefix}.smtc"]

        proc2 = SbyProc(
            task,
            f"engine_{engine_idx}",
            [*task.model("smt2"), witness_proc],
            f"cd {task.workdir}; {task.exe_paths['smtbmc']} {' '.join(smtbmc_opts)} --yw engine_{engine_idx}/{name}{aiw2yw_suffix}.yw model/design_smt2.smt2",
            logfile=open(f"{task.workdir}/engine_{engine_idx}/logfile2.txt", "w"),
        )

        proc2_status = None

        last_prop = []
        current_step = None

        def output_callback2(line):
            nonlocal proc2_status
            nonlocal last_prop
            nonlocal current_step

            smt2_trans = {'\\':'/', '|':'/'}

            def parse_mod_path(path_string):
                # Match a path with . as delimiter, allowing escaped tokens in
                # verilog `\name ` format
                return [m[1] or m[0] for m in re.findall(r"(\\([^ ]*) |[^\.]+)(?:\.|$)", path_string)]

            match = re.match(r"^## [0-9: ]+ .* in step ([0-9]+)\.\.", line)
            if match:
                current_step = int(match[1])
                return line

            match = re.match(r"^## [0-9: ]+ Status: FAILED", line)
            if match: proc2_status = "FAIL"

            match = re.match(r"^## [0-9: ]+ Status: PASSED", line)
            if match: proc2_status = "PASS"

            match = re.match(r"^## [0-9: ]+ Assert failed in ([^:]+): (\S+)(?: \((\S+)\))?", line)
            if match:
                path = parse_mod_path(match[1])
                cell_name = match[3] or match[2]
                prop = task.design.hierarchy.find_property(path, cell_name, trans_dict=smt2_trans)
                prop.status = "FAIL"
                task.status_db.set_task_property_status(prop, data=dict(source="aigsmt", engine=f"engine_{engine_idx}"))
                last_prop.append(prop)
                return line

            match = re.match(r"^## [0-9: ]+ Writing trace to VCD file: (\S+)", line)
            if match:
                tracefile = match[1]
                trace = os.path.basename(tracefile)[:-4]
                task.summary.add_event(engine_idx=engine_idx, trace=trace, path=tracefile)

            if match and last_prop:
                for p in last_prop:
                    task.summary.add_event(
                        engine_idx=engine_idx, trace=trace,
                        type=p.celltype, hdlname=p.hdlname, src=p.location, step=current_step)
                    p.tracefiles.append(tracefile)
                last_prop = []
                return line

            return line

        def exit_callback2(retcode):
            if proc2_status is None:
                task.error(f"engine_{engine_idx}: Could not determine aigsmt status.")
            if proc2_status != "FAIL":
                task.error(f"engine_{engine_idx}: Unexpected aigsmt status.")

        proc2.output_callback = output_callback2
        proc2.register_exit_callback(exit_callback2)

        final_proc = proc2

    if task.opt_fst or (task.opt_vcd and task.opt_vcd_sim):
        final_proc = sim_witness_trace(f"engine_{engine_idx}", task, engine_idx, f"engine_{engine_idx}/{name}.yw", append=sim_append, deps=[final_proc])
    elif not run_aigsmt:
        task.log(f"{click.style(f'engine_{engine_idx}', fg='magenta')}: Engine did not produce a counter example.")

    return final_proc

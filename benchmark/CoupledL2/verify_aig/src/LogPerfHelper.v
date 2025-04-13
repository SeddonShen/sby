`ifndef SIM_TOP_MODULE_NAME
  `define SIM_TOP_MODULE_NAME SimTop
`endif

/*verilator tracing_off*/

module LogPerfHelper (
  output [63:0] timer,
  output        logEnable,
  output        clean,
  output        dump
);

assign timer         = `SIM_TOP_MODULE_NAME.timer;
assign logEnable     = `SIM_TOP_MODULE_NAME.logEnable;
assign clean         = `SIM_TOP_MODULE_NAME.clean;
assign dump          = `SIM_TOP_MODULE_NAME.dump;

endmodule
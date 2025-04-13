
module ResetCounter(
    input clk,
    input reset,
    output [31:0] timeSinceReset,
    output notChaos
);

reg [31:0] count;
reg flag;
initial begin
  count = 0;
  flag = 0;
end

assign timeSinceReset = count;
assign notChaos = flag;

always @(posedge clk) begin
    if (reset) begin
        count <= 0;
        flag <= 1;
    end else if (flag) begin
        count <= count + 1;
    end
end

endmodule
    

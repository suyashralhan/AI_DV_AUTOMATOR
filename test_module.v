module test_module(input wire clk, input wire rst_n, input wire valid, input wire [31:0] data_in, output reg ready);
always@(posedge clk or negedge rst_n)
    begin
        if(!rst_n)
            begin
                ready<= 1'b0;
            end
        else
            begin
                ready <= 1'b1;
            end
    end
endmodule
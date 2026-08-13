module router_fifo #(
    parameter WIDTH = 32,
    parameter DEPTH = 16
)(
    input  logic             clk,
    input  logic             reset_n,
    input  logic             write_en,
    input  logic             read_en,
    input  logic [WIDTH-1:0] data_in,
    output logic            valid_out,
    output logic [WIDTH-1:0] data_out,
    output logic             empty,
    output logic             full
);

    logic [WIDTH-1:0] mem [0:DEPTH-1];
    logic [$clog2(DEPTH)-1:0] wr_ptr, rd_ptr;
    logic [$clog2(DEPTH):0]   count;

    assign full  = (count == DEPTH);
    assign empty = (count == 0);

    always_ff @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
        valid_out <= 0;
            wr_ptr   <= 0;
            rd_ptr   <= 0;
            count    <= 0;
            data_out <= 0;
            for (int i = 0; i < DEPTH; i++) mem[i] <= 0;
        end else begin
            // Write Operation
            if (write_en && !full) begin
                mem[wr_ptr] <= data_in;
                wr_ptr      <= wr_ptr + 1;
            end
            
            // Read Operation
            if (read_en && !empty) begin
                data_out <= mem[rd_ptr];
                rd_ptr   <= rd_ptr + 1;
                valid_out <= 1;
            end

            // Count Management
            if ((write_en && !full) && !(read_en && !empty))
                count <= count + 1;
            else if (!(write_en && !full) && (read_en && !empty))
                count <= count - 1;
                valid_out <= 0;
        end
    end
endmodule
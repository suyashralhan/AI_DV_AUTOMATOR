```systemverilog
module router_fifo_assertions #(
    parameter WIDTH = 32,
    parameter DEPTH = 16
)(
    input  logic             clk,
    input  logic             reset_n,
    input  logic             write_en,
    input  logic             read_en,
    input  logic [WIDTH-1:0] data_in,
    input  logic             valid_out,
    input  logic [WIDTH-1:0] data_out,
    input  logic             empty,
    input  logic             full,
    input  logic [$clog2(DEPTH)-1:0] wr_ptr,
    input  logic [$clog2(DEPTH)-1:0] rd_ptr,
    input  logic [$clog2(DEPTH):0]   count,
    input  logic [WIDTH-1:0] mem [0:DEPTH-1]
);

    // 1. Reset Verification
    // Verifies that on asynchronous reset, all pointers, counters, and status signals are cleared.
    always @(negedge reset_n) begin
        #1ps; // Wait for non-blocking assignments to resolve in simulation
        a_reset_async: assert (
            (wr_ptr == 0) && 
            (rd_ptr == 0) && 
            (count == 0) && 
            (data_out == 0) && 
            (valid_out == 0) && 
            (empty == 1'b1) && 
            (full == 1'b0)
        );
    end

    // 2. Full Flag Assertions
    // Verifies that full is only high when count equals DEPTH.
    property p_full_flag;
        @(posedge clk) disable iff (!reset_n)
        (full == (count == DEPTH));
    endproperty
    a_full_flag: assert property (p_full_flag);

    // 3. Empty Flag Assertions
    // Verifies that empty is only high when count is 0.
    property p_empty_flag;
        @(posedge clk) disable iff (!reset_n)
        (empty == (count == 0));
    endproperty
    a_empty_flag: assert property (p_empty_flag);

    // 4. Count Range Protection
    // Verifies that the FIFO count never exceeds its maximum DEPTH.
    property p_count_range;
        @(posedge clk) disable iff (!reset_n)
        (count <= DEPTH);
    endproperty
    a_count_range: assert property (p_count_range);

    // 5. Write Pointer Progression
    // Verifies that wr_ptr increments on a valid write operation and remains stable otherwise.
    property p_wr_ptr_inc;
        @(posedge clk) disable iff (!reset_n)
        (write_en && !full) |=> (wr_ptr == ($past(wr_ptr) + 1'b1));
    endproperty
    a_wr_ptr_inc: assert property (p_wr_ptr_inc);

    property p_wr_ptr_stable;
        @(posedge clk) disable iff (!reset_n)
        !(write_en && !full) |=> (wr_ptr == $past(wr_ptr));
    endproperty
    a_wr_ptr_stable: assert property (p_wr_ptr_stable);

    // 6. Read Pointer Progression
    // Verifies that rd_ptr increments on a valid read operation and remains stable otherwise.
    property p_rd_ptr_inc;
        @(posedge clk) disable iff (!reset_n)
        (read_en && !empty) |=> (rd_ptr == ($past(rd_ptr) + 1'b1));
    endproperty
    a_rd_ptr_inc: assert property (p_rd_ptr_inc);

    property p_rd_ptr_stable;
        @(posedge clk) disable iff (!reset_n)
        !(read_en && !empty) |=> (rd_ptr == $past(rd_ptr));
    endproperty
    a_rd_ptr_stable: assert property (p_rd_ptr_stable);

    // 7. FIFO Count Progression
    // Verifies correct tracking of item count under all operating conditions.
    property p_count_inc;
        @(posedge clk) disable iff (!reset_n)
        ((write_en && !full) && !(read_en && !empty)) |=> (count == ($past(count) + 1'b1));
    endproperty
    a_count_inc: assert property (p_count_inc);

    property p_count_dec;
        @(posedge clk) disable iff (!reset_n)
        (!(write_en && !full) && (read_en && !empty)) |=> (count == ($past(count) - 1'b1));
    endproperty
    a_count_dec: assert property (p_count_dec);

    property p_count_stable;
        @(posedge clk) disable iff (!reset_n)
        (((write_en && !full) && (read_en && !empty)) || (!(write_en && !full) && !(read_en && !empty))) |=> (count == $past(count));
    endproperty
    a_count_stable: assert property (p_count_stable);

    // 8. Data Storage Integrity
    // Verifies that input data is successfully written into the memory location pointed to by wr_ptr.
    property p_mem_write;
        @(posedge clk) disable iff (!reset_n)
        (write_en && !full) |=> (mem[$past(wr_ptr)] == $past(data_in));
    endproperty
    a_mem_write: assert property (p_mem_write);

    // 9. Data Retrieval Integrity
    // Verifies that data_out correctly outputs the data from the memory location pointed to by rd_ptr.
    property p_data_out_read;
        @(posedge clk) disable iff (!reset_n)
        (read_en && !empty) |=> (data_out == $past(mem[rd_ptr]));
    endproperty
    a_data_out_read: assert property (p_data_out_read);

    // 10. Valid Output Signal Behavior (Will catch the missing begin-end RTL bug)
    // Verifies that valid_out asserts on a successful read operation and deasserts otherwise.
    property p_valid_out_high;
        @(posedge clk) disable iff (!reset_n)
        (read_en && !empty) |=> (valid_out == 1'b1);
    endproperty
    a_valid_out_high: assert property (p_valid_out_high);

    property p_valid_out_low;
        @(posedge clk) disable iff (!reset_n)
        !(read_en && !empty) |=> (valid_out == 1'b0);
    endproperty
    a_valid_out_low: assert property (p_valid_out_low);

endmodule


// Bind statement to attach assertions module to the router_fifo target design
bind router_fifo router_fifo_assertions #(
    .WIDTH(WIDTH),
    .DEPTH(DEPTH)
) i_router_fifo_assertions (
    .clk(clk),
    .reset_n(reset_n),
    .write_en(write_en),
    .read_en(read_en),
    .data_in(data_in),
    .valid_out(valid_out),
    .data_out(data_out),
    .empty(empty),
    .full(full),
    .wr_ptr(wr_ptr),
    .rd_ptr(rd_ptr),
    .count(count),
    .mem(mem)
);
```
```systemverilog
/**
 * Module: router_fifo_assertions
 * Description: SystemVerilog Assertions (SVA) for verification of the router_fifo module.
 * This module checks reset states, empty/full flags, pointer arithmetic, 
 * counter accuracy, and FIFO data integrity.
 */
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
    // Internal RTL signals bound for verification
    input  logic [$clog2(DEPTH)-1:0] wr_ptr,
    input  logic [$clog2(DEPTH)-1:0] rd_ptr,
    input  logic [$clog2(DEPTH):0]   count
);

    //-------------------------------------------------------------------------
    // 1. Reset Verification
    //-------------------------------------------------------------------------
    // Asserts that on asynchronous reset, all registers and outputs are cleared.
    property p_reset_state;
        @(posedge clk) !reset_n |-> 
            (count == 0 && wr_ptr == 0 && rd_ptr == 0 && empty == 1 && full == 0 && valid_out == 0 && data_out == 0);
    endproperty
    a_reset_state: assert property (p_reset_state);

    //-------------------------------------------------------------------------
    // 2. Flag Verification
    //-------------------------------------------------------------------------
    // Asserts that 'empty' flag is set if and only if count is 0.
    property p_empty_flag;
        @(posedge clk) disable iff (!reset_n)
        (count == 0) <-> empty;
    endproperty
    a_empty_flag: assert property (p_empty_flag);

    // Asserts that 'full' flag is set if and only if count equals DEPTH.
    property p_full_flag;
        @(posedge clk) disable iff (!reset_n)
        (count == DEPTH) <-> full;
    endproperty
    a_full_flag: assert property (p_full_flag);

    //-------------------------------------------------------------------------
    // 3. Overflow and Underflow Prevention
    //-------------------------------------------------------------------------
    // Asserts that count never exceeds DEPTH (no overflow).
    property p_no_overflow;
        @(posedge clk) disable iff (!reset_n)
        count <= DEPTH;
    endproperty
    a_no_overflow: assert property (p_no_overflow);

    // Asserts that a write command is not attempted when the FIFO is full.
    // If violated, it indicates upstream protocol issues or lack of flow control.
    property p_no_write_when_full;
        @(posedge clk) disable iff (!reset_n)
        full |-> !write_en;
    endproperty
    a_no_write_when_full: assert property (p_no_write_when_full);

    // Asserts that a read command is not attempted when the FIFO is empty.
    property p_no_read_when_empty;
        @(posedge clk) disable iff (!reset_n)
        empty |-> !read_en;
    endproperty
    a_no_read_when_empty: assert property (p_no_read_when_empty);

    //-------------------------------------------------------------------------
    // 4. Pointer and Counter Management
    //-------------------------------------------------------------------------
    // Asserts that write pointer increments by 1 after a successful write.
    property p_wr_ptr_increment;
        @(posedge clk) disable iff (!reset_n)
        (write_en && !full) |=> (wr_ptr == ($past(wr_ptr) + 1'b1));
    endproperty
    a_wr_ptr_increment: assert property (p_wr_ptr_increment);

    // Asserts that write pointer remains stable when no write occurs.
    property p_wr_ptr_stable;
        @(posedge clk) disable iff (!reset_n)
        !(write_en && !full) |=> (wr_ptr == $past(wr_ptr));
    endproperty
    a_wr_ptr_stable: assert property (p_wr_ptr_stable);

    // Asserts that read pointer increments by 1 after a successful read.
    property p_rd_ptr_increment;
        @(posedge clk) disable iff (!reset_n)
        (read_en && !empty) |=> (rd_ptr == ($past(rd_ptr) + 1'b1));
    endproperty
    a_rd_ptr_increment: assert property (p_rd_ptr_increment);

    // Asserts that read pointer remains stable when no read occurs.
    property p_rd_ptr_stable;
        @(posedge clk) disable iff (!reset_n)
        !(read_en && !empty) |=> (rd_ptr == $past(rd_ptr));
    endproperty
    a_rd_ptr_stable: assert property (p_rd_ptr_stable);

    // Asserts that count increments when only a valid write occurs.
    property p_count_increment;
        @(posedge clk) disable iff (!reset_n)
        ((write_en && !full) && !(read_en && !empty)) |=> (count == $past(count) + 1);
    endproperty
    a_count_increment: assert property (p_count_increment);

    // Asserts that count decrements when only a valid read occurs.
    property p_count_decrement;
        @(posedge clk) disable iff (!reset_n)
        (!(write_en && !full) && (read_en && !empty)) |=> (count == $past(count) - 1);
    endproperty
    a_count_decrement: assert property (p_count_decrement);

    // Asserts that count remains stable when both read and write occur simultaneously, or neither.
    property p_count_stable;
        @(posedge clk) disable iff (!reset_n)
        (((write_en && !full) && (read_en && !empty)) || (!(write_en && !full) && !(read_en && !empty))) |=> (count == $past(count));
    endproperty
    a_count_stable: assert property (p_count_stable);

    //-------------------------------------------------------------------------
    // 5. Output Validity
    //-------------------------------------------------------------------------
    // Asserts that valid_out is asserted on the cycle immediately following a successful read.
    // Note: The RTL has a structural bug where valid_out is unconditionally cleared to 0 in 
    // the count management block because of missing begin/end blocks. This assertion will fail on the RTL,
    // successfully catching the bug.
    property p_valid_out_active;
        @(posedge clk) disable iff (!reset_n)
        (read_en && !empty) |=> (valid_out == 1'b1);
    endproperty
    a_valid_out_active: assert property (p_valid_out_active);

    // Asserts that valid_out remains low when there is no successful read operation.
    property p_valid_out_inactive;
        @(posedge clk) disable iff (!reset_n)
        !(read_en && !empty) |=> (valid_out == 1'b0);
    endproperty
    a_valid_out_inactive: assert property (p_valid_out_inactive);

    //-------------------------------------------------------------------------
    // 6. Data Integrity (FIFO Ordering)
    //-------------------------------------------------------------------------
    // Asserts that the data written at wr_ptr is correctly retrieved when rd_ptr 
    // reaches the same address. Local variables are used to track a specific data transaction.
    property p_fifo_data_integrity;
        logic [WIDTH-1:0] entry_data;
        logic [$clog2(DEPTH)-1:0] entry_addr;
        @(posedge clk) disable iff (!reset_n)
        ((write_en && !full), entry_data = data_in, entry_addr = wr_ptr) |->
        first_match(##[1:$] (read_en && !empty && rd_ptr == entry_addr)) |=> (data_out == entry_data);
    endproperty
    a_fifo_data_integrity: assert property (p_fifo_data_integrity);

endmodule


/**
 * Bind Statement
 * Hooks up the assertion module to the design under test (DUT).
 */
bind router_fifo router_fifo_assertions #(
    .WIDTH(WIDTH),
    .DEPTH(DEPTH)
) router_fifo_assert_inst (
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
    .count(count)
);
```
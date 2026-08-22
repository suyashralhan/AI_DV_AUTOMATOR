```systemverilog
// =========================================================================
// SYSTEMVERILOG ASSERTIONS FOR ROUTER_CROSSBAR
// =========================================================================

module router_crossbar_assertions (
    input  logic             clk,
    input  logic             reset_n,
    input  logic [31:0]      fifo_data [4],
    input  logic             fifo_empty [4],
    input  logic             fifo_read [4],
    input  logic [31:0]      out_data [4],
    input  logic             out_valid [4]
);

    // Internal reconstruction of destination addresses for assertion logic
    logic [1:0] dest_addr [4];
    always_comb begin
        for (int i = 0; i < 4; i++) begin
            dest_addr[i] = fifo_data[i][31:30];
        end
    end

    // -------------------------------------------------------------------------
    // Rule 1: UNDERFLOW PREVENTION (Adapted from Protocol Specification Rule 2)
    // The 'fifo_read' signal must never be asserted when the 'fifo_empty' signal is high.
    // -------------------------------------------------------------------------
    generate
        for (genvar i = 0; i < 4; i++) begin : gen_underflow_check
            assert_underflow_prevent: assert property (
                @(posedge clk) disable iff (!reset_n)
                (fifo_empty[i] |-> !fifo_read[i])
            ) else $error("UNDERFLOW ERROR: fifo_read[%0d] asserted while fifo_empty[%0d] is high!", i, i);
        end
    endgenerate

    // -------------------------------------------------------------------------
    // Rule 2: ASYNCHRONOUS RESET STATE
    // When reset_n is active low, all outputs and read-enables must be immediately cleared.
    // -------------------------------------------------------------------------
    generate
        for (genvar i = 0; i < 4; i++) begin : gen_reset_check
            assert_reset_state: assert property (
                @(posedge clk) (!reset_n |-> (out_data[i] == 32'h0 && out_valid[i] == 1'b0 && fifo_read[i] == 1'b0))
            ) else $error("RESET ERROR: Output registers not cleared on reset for port %0d!", i);
        end
    endgenerate

    // -------------------------------------------------------------------------
    // Rule 3: ROUTING & DATA INTEGRITY
    // If out_valid[out_idx] is asserted, the output data must match the data 
    // of one of the active input FIFOs targeting this specific output port.
    // -------------------------------------------------------------------------
    generate
        for (genvar out_idx = 0; out_idx < 4; out_idx++) begin : gen_routing_check
            assert_valid_out_data_match: assert property (
                @(posedge clk) disable iff (!reset_n)
                (out_valid[out_idx] |-> 
                    ((dest_addr[0] == out_idx && out_data[out_idx] == fifo_data[0]) ||
                     (dest_addr[1] == out_idx && out_data[out_idx] == fifo_data[1]) ||
                     (dest_addr[2] == out_idx && out_data[out_idx] == fifo_data[2]) ||
                     (dest_addr[3] == out_idx && out_data[out_idx] == fifo_data[3]))
                )
            ) else $error("ROUTING ERROR: out_data[%0d] does not match any valid source FIFO data!", out_idx);
        end
    endgenerate

    // -------------------------------------------------------------------------
    // Rule 4: READ AND VALID CO-ASSERTION
    // Whenever a FIFO read is performed, the corresponding output channel 
    // specified by the destination address must assert its valid signal.
    // -------------------------------------------------------------------------
    generate
        for (genvar i = 0; i < 4; i++) begin : gen_read_implies_valid
            assert_read_implies_valid: assert property (
                @(posedge clk) disable iff (!reset_n)
                (fifo_read[i] |-> out_valid[dest_addr[i]])
            ) else $error("PROTOCOL ERROR: fifo_read[%0d] is high but out_valid[%0d] is low!", i, dest_addr[i]);
        end
    endgenerate

    // -------------------------------------------------------------------------
    // Rule 5: MUTUAL EXCLUSION OF ARBITRATION
    // Ensure that multiple input ports do not read from the same FIFO in the same cycle.
    // This is structurally guaranteed but formally verified here.
    // -------------------------------------------------------------------------
    generate
        for (genvar i = 0; i < 4; i++) begin : gen_one_hot_read
            assert_fifo_read_one_hot: assert property (
                @(posedge clk) disable iff (!reset_n)
                (fifo_read[i] |-> $onehot(fifo_read))
            ) else $error("ARBITRATION ERROR: Multiple reads or invalid state detected on fifo_read array!");
        end
    endgenerate

endmodule

// =========================================================================
// BIND STATEMENT FOR SYSTEMVERILOG ASSERTIONS
// =========================================================================
bind router_crossbar router_crossbar_assertions inst_router_crossbar_assertions (
    .clk(clk),
    .reset_n(reset_n),
    .fifo_data(fifo_data),
    .fifo_empty(fifo_empty),
    .fifo_read(fifo_read),
    .out_data(out_data),
    .out_valid(out_valid)
);
```
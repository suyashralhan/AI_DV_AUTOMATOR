```systemverilog
// ============================================================================
// 1. SYNCHRONOUS FIFO PROTOCOL ASSERTIONS
// This module implements the strict SVA checks specified in the protocol rules.
// It can be bound to any standard synchronous FIFO used in the system design.
// ============================================================================
module sync_fifo_assertions #(
    parameter DEPTH = 16,
    parameter ADDR_WIDTH = $clog2(DEPTH)
)(
    input  logic                  clk,
    input  logic                  rst_n,
    input  logic                  wr_en,
    input  logic                  rd_en,
    input  logic                  full,
    input  logic                  empty,
    input  logic [ADDR_WIDTH-1:0] wr_ptr,
    input  logic [ADDR_WIDTH:0]   data_cnt
);

    // RULE 1: OVERFLOW
    // The 'wr_en' signal must never be asserted when the 'full' signal is high.
    property p_fifo_overflow;
        @(posedge clk) disable iff (!rst_n)
        full |-> !wr_en;
    endproperty
    assert_fifo_overflow: assert property (p_fifo_overflow)
        else $error("FIFO Protocol Violation: wr_en asserted when FIFO is full (Overflow)");

    // RULE 2: UNDERFLOW
    // The 'rd_en' signal must never be asserted when the 'empty' signal is high.
    property p_fifo_underflow;
        @(posedge clk) disable iff (!rst_n)
        empty |-> !rd_en;
    endproperty
    assert_fifo_underflow: assert property (p_fifo_underflow)
        else $error("FIFO Protocol Violation: rd_en asserted when FIFO is empty (Underflow)");

    // RULE 3: POINTER WRAP
    // When the write pointer reaches the maximum depth, it must wrap around to 0.
    property p_pointer_wrap;
        @(posedge clk) disable iff (!rst_n)
        (wr_en && !full && (wr_ptr == DEPTH - 1)) |=> (wr_ptr == 0);
    endproperty
    assert_pointer_wrap: assert property (p_pointer_wrap)
        else $error("FIFO Protocol Violation: wr_ptr did not wrap to 0 after reaching DEPTH-1");

    // RULE 4: SIMULTANEOUS ACCESS
    // If 'wr_en' and 'rd_en' are asserted simultaneously when the FIFO is neither full nor empty,
    // the data count should remain unchanged.
    property p_simultaneous_access;
        @(posedge clk) disable iff (!rst_n)
        (wr_en && rd_en && !full && !empty) |=> (data_cnt == $past(data_cnt));
    endproperty
    assert_simultaneous_access: assert property (p_simultaneous_access)
        else $error("FIFO Protocol Violation: data_cnt changed during simultaneous wr_en and rd_en when not full/empty");

endmodule


// ============================================================================
// 2. ROUTER CROSSBAR ASSERTIONS
// This module checks correct functionality, routing, reset behavior, and
// underflow prevention specifically on the provided router_crossbar RTL.
// ============================================================================
module router_crossbar_assertions (
    input  logic             clk,
    input  logic             reset_n,
    input  logic [31:0]      fifo_data [4],
    input  logic             fifo_empty [4],
    input  logic             fifo_read [4],
    input  logic [31:0]      out_data [4],
    input  logic             out_valid [4]
);

    // RULE 2 (UNDERFLOW CHECK ON INTERFACE):
    // The crossbar must never request a read (fifo_read) when the source FIFO is empty.
    generate
        for (genvar i = 0; i < 4; i++) begin : gen_underflow_check
            assert_crossbar_underflow: assert property (
                @(posedge clk) disable iff (!reset_n)
                fifo_empty[i] |-> !fifo_read[i]
            ) else $error("Crossbar Interface Violation: fifo_read[%0d] asserted when fifo_empty[%0d] is high", i, i);
        end
    endgenerate

    // RESET STATE CHECK:
    // Upon reset assertion, all control and output data registers must be cleared on the next active edge.
    property p_reset_state;
        @(posedge clk) !reset_n |-> (
            (out_data[0] == 32'h0) && (out_valid[0] == 1'b0) && (fifo_read[0] == 1'b0) &&
            (out_data[1] == 32'h0) && (out_valid[1] == 1'b0) && (fifo_read[1] == 1'b0) &&
            (out_data[2] == 32'h0) && (out_valid[2] == 1'b0) && (fifo_read[2] == 1'b0) &&
            (out_data[3] == 32'h0) && (out_valid[3] == 1'b0) && (fifo_read[3] == 1'b0)
        );
    endproperty
    assert_reset_state: assert property (p_reset_state)
        else $error("Crossbar Reset Violation: Outputs and read enables not cleared on active reset");

    // ROUTING CORRECTNESS:
    // Whenever out_valid[j] is asserted, the routed out_data[j] must correctly originate 
    // from one of the active input FIFOs with matching destination address [31:30].
    generate
        for (genvar j = 0; j < 4; j++) begin : gen_routing_check
            assert_routing_correctness: assert property (
                @(posedge clk) disable iff (!reset_n)
                out_valid[j] |-> (
                    (fifo_read[0] && ($past(fifo_data[0][31:30]) == j) && (out_data[j] == $past(fifo_data[0]))) ||
                    (fifo_read[1] && ($past(fifo_data[1][31:30]) == j) && (out_data[j] == $past(fifo_data[1]))) ||
                    (fifo_read[2] && ($past(fifo_data[2][31:30]) == j) && (out_data[j] == $past(fifo_data[2]))) ||
                    (fifo_read[3] && ($past(fifo_data[3][31:30]) == j) && (out_data[j] == $past(fifo_data[3])))
                )
            ) else $error("Crossbar Routing Violation: out_valid[%0d] asserted with incorrect or unauthorized data", j);
        end
    endgenerate

    // ARBITRATION PRIORITY:
    // Check that priority is strictly observed: Input 0 > Input 1 > Input 2 > Input 3.
    // If a higher priority input targets output 'j' and is not blocked by previous reads,
    // lower priority requests for the same output must not be granted.
    generate
        for (genvar j = 0; j < 4; j++) begin : gen_priority_check
            // Input 0 has priority over Input 1
            assert_priority_0_over_1: assert property (
                @(posedge clk) disable iff (!reset_n)
                (!fifo_empty[0] && ($past(fifo_data[0][31:30]) == j) && !fifo_read[0]) |-> !fifo_read[1] || ($past(fifo_data[1][31:30]) != j)
            ) else $error("Crossbar Priority Violation: Input 1 routed to port %0d when Input 0 had higher priority", j);

            // Inputs 0 & 1 have priority over Input 2
            assert_priority_01_over_2: assert property (
                @(posedge clk) disable iff (!reset_n)
                ((!fifo_empty[0] && ($past(fifo_data[0][31:30]) == j) && !fifo_read[0]) ||
                 (!fifo_empty[1] && ($past(fifo_data[1][31:30]) == j) && !fifo_read[1]))
                |-> !fifo_read[2] || ($past(fifo_data[2][31:30]) != j)
            ) else $error("Crossbar Priority Violation: Input 2 routed to port %0d when Input 0 or 1 had higher priority", j);

            // Inputs 0, 1 & 2 have priority over Input 3
            assert_priority_012_over_3: assert property (
                @(posedge clk) disable iff (!reset_n)
                ((!fifo_empty[0] && ($past(fifo_data[0][31:30]) == j) && !fifo_read[0]) ||
                 (!fifo_empty[1] && ($past(fifo_data[1][31:30]) == j) && !fifo_read[1]) ||
                 (!fifo_empty[2] && ($past(fifo_data[2][31:30]) == j) && !fifo_read[2]))
                |-> !fifo_read[3] || ($past(fifo_data[3][31:30]) != j)
            ) else $error("Crossbar Priority Violation: Input 3 routed to port %0d when higher priority inputs had active requests", j);
        end
    endgenerate

endmodule


// ============================================================================
// 3. BIND STATEMENT
// Binds the router_crossbar_assertions directly to the target RTL.
// ============================================================================
bind router_crossbar router_crossbar_assertions u_router_crossbar_assertions (.*);
```
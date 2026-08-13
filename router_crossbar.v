module router_crossbar (
    input  logic             clk,
    input  logic             reset_n,
    
    // Data from input FIFOs
    input  logic [31:0]      fifo_data [4],
    input  logic             fifo_empty [4],
    output logic             fifo_read [4],
    
    // Output Ports
    output logic [31:0]      out_data [4],
    output logic             out_valid [4]
);

    logic [1:0] dest_addr [4];
    
    // Extract destination addresses from the front of each FIFO
    always_comb begin
        for (int i = 0; i < 4; i++) begin
            dest_addr[i] = fifo_data[i][31:30];
        end
    end

    always_ff @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            for (int i = 0; i < 4; i++) begin
                out_data[i]  <= 32'h0;
                out_valid[i] <= 1'b0;
                fifo_read[i] <= 1'b0;
            end
        end else begin
            // Default: nothing is valid, no reads
            for (int i = 0; i < 4; i++) begin
                out_valid[i] <= 1'b0;
                fifo_read[i] <= 1'b0;
            end

            // Arbitration: For each output port (0 to 3), find the highest priority input
            for (int out_idx = 0; out_idx < 4; out_idx++) begin
                if (!fifo_empty[0] && dest_addr[0] == out_idx && !fifo_read[0]) begin
                    out_data[out_idx]  <= fifo_data[0];
                    out_valid[out_idx] <= 1'b1;
                    fifo_read[0]       <= 1'b1;
                end 
                else if (!fifo_empty[1] && dest_addr[1] == out_idx && !fifo_read[1]) begin
                    out_data[out_idx]  <= fifo_data[1];
                    out_valid[out_idx] <= 1'b1;
                    fifo_read[1]       <= 1'b1;
                end
                else if (!fifo_empty[2] && dest_addr[2] == out_idx && !fifo_read[2]) begin
                    out_data[out_idx]  <= fifo_data[2];
                    out_valid[out_idx] <= 1'b1;
                    fifo_read[2]       <= 1'b1;
                end
                else if (!fifo_empty[3] && dest_addr[3] == out_idx && !fifo_read[3]) begin
                    out_data[out_idx]  <= fifo_data[3];
                    out_valid[out_idx] <= 1'b1;
                    fifo_read[3]       <= 1'b1;
                end
            end
        end
    end
endmodule
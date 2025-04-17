from flask import Flask, render_template, request, jsonify
import numpy as np
import networkx as nx

app = Flask(__name__)

def is_safe_state(processes, resources, allocation, max_demand, available):
    allocation = np.array(allocation)
    max_demand = np.array(max_demand)
    available = np.array(available)
    need = max_demand - allocation
    work = available.copy()
    finish = [False] * len(processes)
    safe_sequence = []

    while len(safe_sequence) < len(processes):
        allocated = False
        for i in range(len(processes)):
            if not finish[i] and all(need[i, j] <= work[j] for j in range(len(resources))):
                work += allocation[i]
                finish[i] = True
                safe_sequence.append(processes[i])
                allocated = True
        if not allocated:
            return False, []
    return True, safe_sequence

def detect_deadlock(processes, resources, allocation, max_demand, available):
    G = nx.DiGraph()
    
    allocation = np.array(allocation)
    max_demand = np.array(max_demand)
    available = np.array(available)
    need = max_demand - allocation

    # First check: If no resources are available and all processes need resources
    if np.all(available == 0):
        all_processes_need = True
        for i in range(len(processes)):
            if np.all(need[i] == 0):
                all_processes_need = False
                break
        if all_processes_need:
            # All processes need resources but none are available
            return True, [(p, "Resources") for p in processes]

    # Add process and resource nodes
    for p in processes:
        G.add_node(p, color='blue')
    for r in resources:
        G.add_node(r, color='red')

    # Add edges based on resource allocation and needs
    for i, process in enumerate(processes):
        for j, res in enumerate(resources):
            if need[i][j] > 0 and allocation[i][j] == 0 and available[j] == 0:
                # Process needs a resource but it's not available (waiting edge)
                G.add_edge(process, res)
            if allocation[i][j] > 0:
                # Process is holding a resource (holding edge)
                G.add_edge(res, process)

    # Detect cycles in the resource allocation graph
    try:
        cycle = list(nx.find_cycle(G, orientation='original'))
        return True, cycle
    except nx.NetworkXNoCycle:
        return False, []

def validate_input(processes, resources, allocation, max_demand, available):
    """
    Validates the input according to Banker's Algorithm rules
    Returns (is_valid, error_message)
    """
    try:
        allocation = np.array(allocation)
        max_demand = np.array(max_demand)
        available = np.array(available)
        
        # Check dimensions match
        if len(processes) != len(allocation):
            return False, f"Number of processes ({len(processes)}) doesn't match allocation matrix rows ({len(allocation)})"
        
        if len(resources) != len(allocation[0]):
            return False, f"Number of resources ({len(resources)}) doesn't match allocation matrix columns ({len(allocation[0])})"
            
        if len(max_demand) != len(allocation):
            return False, "Max demand matrix dimensions don't match allocation matrix"
            
        # Check allocation ≤ max_demand
        for i in range(len(processes)):
            for j in range(len(resources)):
                if allocation[i][j] > max_demand[i][j]:
                    return False, f"Invalid: Process {processes[i]} is allocated {allocation[i][j]} units of resource {resources[j]}, but declared max need is {max_demand[i][j]}"
        
        # Check if total allocated + available resources is non-negative
        total_allocated = np.sum(allocation, axis=0)
        if not all(available[j] >= 0 for j in range(len(resources))):
            return False, "Available resources cannot be negative"
            
        return True, ""
        
    except Exception as e:
        return False, f"Invalid input format: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/simulate', methods=['POST'])
def simulate():
    try:
        data = request.json
        processes = data['processes']
        resources = data['resources']
        allocation = data['allocation']
        max_demand = data['max_demand']
        available = data['available']

        # Validate input first
        is_valid, error_message = validate_input(processes, resources, allocation, max_demand, available)
        if not is_valid:
            return jsonify({
                "error": error_message,
                "safe_state": False,
                "safe_sequence": [],
                "deadlock_detected": False,
                "deadlock_cycle": []
            }), 400

        # Calculate additional metrics
        allocation_np = np.array(allocation)
        max_demand_np = np.array(max_demand)
        available_np = np.array(available)
        
        # Calculate resource utilization
        total_allocated = np.sum(allocation_np, axis=0)
        total_available = available_np
        total_resources = total_allocated + total_available
        utilization = (total_allocated / total_resources * 100).tolist()

        # Calculate process states
        need = max_demand_np - allocation_np
        process_states = []
        for i in range(len(processes)):
            if np.all(need[i] == 0):
                state = "Complete"
            elif np.any(allocation_np[i] > 0):
                state = "Running"
            else:
                state = "Waiting"
            process_states.append(state)

        safe, sequence = is_safe_state(processes, resources, allocation, max_demand, available)
        deadlock, cycle = detect_deadlock(processes, resources, allocation, max_demand, available)

        return jsonify({
            "safe_state": safe,
            "safe_sequence": sequence if safe else [],
            "deadlock_detected": deadlock,
            "deadlock_cycle": cycle if deadlock else [],
            "metrics": {
                "resource_utilization": utilization,
                "process_states": process_states,
                "total_resources": total_resources.tolist(),
                "total_allocated": total_allocated.tolist(),
                "total_available": total_available.tolist()
            }
        })

    except Exception as e:
        return jsonify({
            "error": f"Server error: {str(e)}",
            "safe_state": False,
            "safe_sequence": [],
            "deadlock_detected": False,
            "deadlock_cycle": [],
            "metrics": {}
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
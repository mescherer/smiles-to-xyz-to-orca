# This file contains the code to make a highly efficient SLURM .sh and ORCA .inp file
# for the computing cluster. This is designed to be used in conjunction with job.py to provide
# a streamlined job submission process.

import os

def orca_script(variables):
    
    # Unpack variables
    xyz_file = variables['xyz_file']
    job_name = variables['job_name']
    charge = variables['charge']
    mult = variables['mult']
    params = variables['params']
    job_type = variables['job_type']

    nodes = params['nodes']
    ntasks_per_node = int(params['ntasks_per_node'])
    mem = params['mem']
    time = params['time']
    partition = params['partition']
    solvent_inp = params['solvent']
    
    # 1. FILE STAGING FIX: Get absolute path to guarantee we copy the right file
    xyz_abs_path = os.path.abspath(xyz_file)
    xyz_filename = os.path.basename(xyz_file)
        
    # 2. MEMORY FIX: Dynamically calculate maxcore
    # Strip non-numeric characters (e.g., "64GB" -> 64) and convert to MB
    total_mem_gb = float(''.join(filter(str.isdigit, mem)))
    total_mem_mb = total_mem_gb * 1024
    
    # Leave 15% buffer for MPI overhead, divide by cores
    safe_mem_mb = total_mem_mb * 0.85
    maxcore = int(safe_mem_mb // ntasks_per_node)
    
    # Calculate workers
    n_workers = ntasks_per_node // 4
    
    # Determine script based on job type
    if job_type == 'goat':
        inp_content = goat_script(solvent_inp, ntasks_per_node, maxcore, n_workers, charge, mult, xyz_filename)
    elif job_type == 'single_point':
        inp_content = single_point_script(variables)
    elif job_type == 'geom_opt':
        inp_content = geom_opt_script(variables)
    elif job_type == 'vib':
        inp_content = vib_script(variables)
    
    # Slurm Template for ORCA
    sh_content = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node={ntasks_per_node}
#SBATCH --mem={mem}
#SBATCH --time={time}
#SBATCH --partition={partition}

module load chemistry orca/6.1.0

JOB_NAME="{job_name}"
SUBMIT_DIR=$SLURM_SUBMIT_DIR

# Stage exact coordinate file into the node's official local SSD space
cp "{xyz_abs_path}" "$L_SCRATCH_JOB/"

# State the ORCA input file into the scratch space
cp "$SUBMIT_DIR/$JOB_NAME.inp" "$L_SCRATCH_JOB/"

cd "$L_SCRATCH_JOB"

# Run the calculation detached from the network file system
$(which orca) "$JOB_NAME.inp" > "$SUBMIT_DIR/$JOB_NAME.out"

# Pull all GOAT coordinate and trajectory outputs back
cp "$JOB_NAME"*.xyz "$SUBMIT_DIR/" 2>/dev/null || true
"""
    return inp_content, sh_content

def goat_script(solvent_inp, ntasks_per_node, maxcore, n_workers, charge, mult, xyz_filename):
    # (Watch out for Python 'None' type vs the string 'None' from argparse)
    if solvent_inp == 'None' or solvent_inp is None:
        solvent = ''
    else:
        solvent = f'ALPB({solvent_inp})'

    # For ORCA GOAT Conformer Search
    inp_content = f"""! GOAT XTB {solvent}

%pal nprocs {ntasks_per_node} end
%maxcore {maxcore}                              # Dynamically set to prevent SLURM OOM

%GOAT
    NWorkers {n_workers}                        # Divides cores into {n_workers} concurrent pipelines
    MaxEn 5.0                                   # Immediately drop conformers > 5 kcal/mol
    GFNUphill GFNFF                             # Acceleration trick
end

* xyzfile {charge} {mult} {xyz_filename}
"""
    return inp_content

def orca_single_point_script(variables):
    return "", ""
def orca_geom_opt_script(variables):
    return "", ""
def orca_vib_script(variables):
    return "", ""
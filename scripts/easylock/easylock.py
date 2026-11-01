# This file creates an automated submission pipeline for
# jobs on the computing cluster. This is an interactive script.
# From the users desired directory in the cluster, it prompts the 
# user for job parameters, creates the appropriate job input 
# and submission scripts, and submits the job to the Slurm scheduler.

import argparse
import os
import subprocess
import sys
import json
from tools.smiles_to_xyz import generate_conformer
from tools.write_script import orca_script
import rdkit
from rdkit import Chem

def build_parser():
    parser = argparse.ArgumentParser(description="Script that inputs chemical structures and submits an ORCA GOAT job.")
    
    # 1. Core Run Variables (Frequently changed, required)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--xyz", type=str, help="Path to an existing .xyz file")
    input_group.add_argument("--smiles", type=str, help="SMILES string to convert to 3D coordinates")

    parser.add_argument("--charge", type=int, required=True, help="Molecular formal charge (required)")
    parser.add_argument("--mult", type=int, required=True, help="Spin multiplicity (required)")
    parser.add_argument("--name", type=str, required=True, help="Name of the job (required)")
    parser.add_argument("--job-type", type=str, required=True, help="Type of ORCA job to run. (options: 'goat', 'single_point', 'geom_opt', 'vib')")
    
    # 2. Profile Architecture Arguments
    # Anchor the config file to the script's actual directory
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    DEFAULT_CONFIG = os.path.join(SCRIPT_DIR, "configs.json")
    
    parser.add_argument("--config-file", type=str, default=DEFAULT_CONFIG, 
                        help="Path to the master JSON file")
    parser.add_argument("--profile", type=str, 
                        help="Name of the configuration profile to load (e.g., 'xtb_quick')")
    parser.add_argument("--save-profile", type=str, 
                        help="Save the final executed parameters as a new profile under this name")

    # 3. Cluster Parameters (Default must be None to detect CLI overrides)
    parser.add_argument("--nodes", type=int, help="Number of nodes")
    parser.add_argument("--ntasks-per-node", type=int, dest="ntasks_per_node", help="Cores per node")
    parser.add_argument("--mem", type=str, help="Total memory per node (e.g., 32GB)")
    parser.add_argument("--time", type=str, help="Wall-time limit (e.g., 04:00:00)")
    parser.add_argument("--partition", type=str, help="Slurm partition to target")
    parser.add_argument("--solvent", type=str, help="Implicit solvent name (e.g., Water or None)")
    
    return parser

def get_vars():
    parser = build_parser()
    args = parser.parse_args()

    # Decide What Input File to Use
    job_name = args.name
    if args.smiles:
        xyz_file = f"{job_name}.xyz"
        print(f"Generating 3D coordinates from SMILES: {xyz_file}")
        mol = generate_conformer(args.smiles)
        Chem.MolToXYZFile(mol, xyz_file)
        print(f"Success! {xyz_file} created.")
    else:
        xyz_file = args.xyz

    # Define the lowest-priority fallback defaults
    final_params = {
        "nodes": 1,
        "ntasks_per_node": 8,
        "mem": "32GB",
        "time": "02:00:00",
        "partition": "normal",
        "solvent": "None"
    }

    # Load Master Config File & Requested Profile
    master_configs = {}
    if os.path.exists(args.config_file):
        with open(args.config_file, 'r') as f:
            try:
                master_configs = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: '{args.config_file}' is invalid or empty. Starting fresh.")
    
    if args.profile:
        if args.profile in master_configs:
            final_params.update(master_configs[args.profile])  # Merge profile settings
            print(f"Loaded profile '{args.profile}' from {args.config_file}")
        else:
            print(f"Warning: Profile '{args.profile}' not found. Using baseline defaults.")

    # Command-Line Overrides (Highest priority)
    cli_overrides = {
        "nodes": args.nodes,
        "ntasks_per_node": args.ntasks_per_node,
        "mem": args.mem,
        "time": args.time,
        "partition": args.partition,
        "solvent": args.solvent
    }
    
    for key, value in cli_overrides.items():
        if value is not None:
            final_params[key] = value

    # Handle Dynamic Job Name
    job_name = args.name

    # Save Profile if requested
    if args.save_profile:
        # Update the master dictionary with the new/modified profile block
        master_configs[args.save_profile] = final_params
        
        # Dump the entire master dictionary back into the single JSON file
        with open(args.config_file, 'w') as f:
            json.dump(master_configs, f, indent=4)
        print(f"Successfully saved new profile '{args.save_profile}' to {args.config_file}")

    # --- Job Execution Execution ---
    print("\n--- Final Job Submission Parameters ---")
    print(f"Target XYZ : {xyz_file}")
    print(f"Job Name   : {job_name}")
    print(f"Charge/Mult: {args.charge} / {args.mult}")
    print(f"Job Type   : {args.job_type}")
    print("Cluster Settings:")
    for k, v in final_params.items():
        print(f"  {k}: {v}")

    variables = {
        'xyz_file': xyz_file, 
        'job_name': job_name, 
        'charge': args.charge, 
        'mult': args.mult, 
        'params': final_params,
        'job_type': args.job_type
    }
    
    return variables

def write_submit_files(inp_content, sh_content, name):
    # write the script to the file
    inp_file = f"{name}.inp"
    sh_file = f"{name}.sh"
    with open(inp_file, "w") as f:
        f.write(inp_content)
    with open(sh_file, "w") as f:
        f.write(sh_content)

    # submit the script safely
    try:
        subprocess.run(["sbatch", sh_file], check=True)
        print(f"--- Job {name} Successfully Submitted! ---")
    except subprocess.CalledProcessError as e:
        print(f"Error: SLURM failed to submit the job. Details:\n{e}")

def main():
    variables = get_vars()
    name = variables['job_name']
    inp_content, sh_content = orca_script(variables)
    write_submit_files(inp_content, sh_content, name)

if __name__ == "__main__":
    main()
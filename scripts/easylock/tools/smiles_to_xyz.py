# This file contains the code to generate a 3D conformer from a SMILES string.

from rdkit import Chem
from rdkit.Chem import AllChem
import argparse
import sys

def generate_conformer(smiles_string):
    mol = Chem.MolFromSmiles(smiles_string)
    
    # Safety check: Ensure the SMILES string is valid and parsed correctly
    if mol is None:
        print(f"Error: RDKit could not parse the SMILES string: '{smiles_string}'")
        sys.exit(1)
        
    mol = Chem.AddHs(mol)
    
    # Configure the ETKDGv3 parameters cleanly to avoid C++ signature mismatch
    params = AllChem.ETKDGv3()
    params.maxIterations = 200
    
    # Attempt 3D embedding
    status = AllChem.EmbedMolecule(mol, params)
    
    # Fallback to random coordinates if the initial embedding fails
    if status == -1:
        print("Warning: Standard 3D embedding failed. Retrying with random coordinates...")
        params.useRandomCoords = True
        status_fallback = AllChem.EmbedMolecule(mol, params)
        if status_fallback == -1:
            print("Error: Could not generate 3D coordinates even with random initialization.")
            sys.exit(1)
            
    # Clean up geometry using MMFF94 force field
    AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
    return mol

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a 3D conformer from a SMILES string")
    parser.add_argument("smiles_string", help="The SMILES string of the molecule")
    parser.add_argument("name", help="The name of the molecule (for the .xyz file)")
    args = parser.parse_args()
    
    mol = generate_conformer(args.smiles_string)
    
    output_filename = args.name + ".xyz"
    Chem.MolToXYZFile(mol, output_filename)
    print(f"Successfully wrote 3D coordinates to {output_filename}")
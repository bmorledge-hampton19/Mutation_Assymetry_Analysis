# This script will, when given a bed formatted file with mutation entries,
# create a bed file with an expanded tri/pentanucleotide context around the mutation.

import os
from nucperiodpy.Tkinter_scripts.TkinterDialog import TkinterDialog, Selections
from nucperiodpy.helper_scripts.UsefulBioinformaticsFunctions import bedToFasta, FastaFileIterator
from nucperiodpy.helper_scripts.UsefulFileSystemFunctions import Metadata, generateFilePath, DataTypeStr, getContext, getDataDirectory


# Expands the range of each mutation position in the original mutation file to encompass one extra base on either side.
def expandBedPositions(inputBedFilePath,bedExpansionFilePath,contextNum):
    "Expands the range of each mutation position in the original mutation file to encompass one extra base on either side."

    with open(bedExpansionFilePath,'w') as bedExpansionFile:
        with open(inputBedFilePath, 'r') as inputBedFile:

            print("Writing expanded mutation indicies to intermediate bed file...")
            for line in inputBedFile:

                # Get a list of all the arguments for a single mutation in the bed file.
                choppedUpLine = line.strip().split('\t')

                # Find the middle base of the sequence specified by the bed file.
                middleBaseNum = int((int(choppedUpLine[1]) + int(choppedUpLine[2]) - 1) / 2)

                # Expand the position of the mutation to create the desired context.
                choppedUpLine[1] = str(middleBaseNum - int(contextNum/2))
                choppedUpLine[2] = str(middleBaseNum + int(contextNum/2) + 1)

                # Write the results to the intermediate expansion file as long as it is not at the start of the chromosome.
                if int(choppedUpLine[1]) > -1: bedExpansionFile.write("\t".join(choppedUpLine)+"\n")
                else: print("Mutation at chromosome", choppedUpLine[0], "with expanded start pos", choppedUpLine[1],
                            "extends into invalid positions.  Skipping.")


# Uses the expanded reads fasta file to create a new bed file with the expanded mutational context.
def generateExpandedContext(inputBedFilePath,fastaReadsFilePath,expandedContextFilePath,contextNum):
    "Uses the expanded reads fasta file to create a new bed file with the expanded mutational context."

    print("Using fasta file to write expanded context to new bed file...")
    # Open the singlenuc context bed file and the expanded fasta reads that will be combined to create the expanded context.
    with open(inputBedFilePath, 'r') as inputBedFile:
        with open(fastaReadsFilePath, 'r') as fastaReadsFile:
            with open(expandedContextFilePath, 'w') as expandedContextFile:

                # Work through the singlenuc context bed file one mutation at a time.
                for fastaEntry in FastaFileIterator(fastaReadsFile):

                    # Find the singlenuc entry corresponding to this entry.
                    while True:

                        # Read in the next line
                        nextLine = inputBedFile.readline()

                        # If we reached the end of the file without finding a match, we have a problem...
                        if len(nextLine) == 0:
                            raise ValueError("Reached end of single base bed file without finding a match for:",fastaEntry.sequenceLocation)

                        # Split the next line on tab characters and check for a match with the current read in the fasta file.
                        choppedUpLine = nextLine.strip().split("\t")
                        if (str(int(fastaEntry.startPos)+int(contextNum/2)) == choppedUpLine[1] and fastaEntry.chromosome == choppedUpLine[0] and 
                            fastaEntry.strand == choppedUpLine[5]): break

                    # Replace the mutation's singlenuc context with the expanded context.
                    choppedUpLine[3] = fastaEntry.sequence

                    # Write the result to the new expanded context file.
                    expandedContextFile.write("\t".join(choppedUpLine)+"\n")


def expandContext(inputBedFilePaths, expansionContextNum):
    
    expandedContextFilePaths = list() # A list of paths to the output files generated by the function

    # Set the name of the type of context being used.
    if expansionContextNum == 3: contextText = "trinuc"
    elif expansionContextNum == 5: contextText = "pentanuc"
    else: raise ValueError("Unexpected expansion context number: " + str(expansionContextNum))

    for inputBedFilePath in inputBedFilePaths:

        # Retrieve metadata
        metadata = Metadata(inputBedFilePath)

        # Make sure file names look valid.
        print("\nWorking in:",os.path.split(inputBedFilePath)[1])
        if not DataTypeStr.mutations in os.path.split(inputBedFilePath)[1]:
            raise ValueError("Error:  Expected file with \"" + DataTypeStr.mutations + "\" in the name.")
        
        # Make sure the context of the input bed file is less than the expansion context.
        if getContext(inputBedFilePath, asInt = True) >= expansionContextNum:
            raise ValueError("The input bed file at " + inputBedFilePath + 
                             " does not have a lower context than the desired output context.")

        # Generate paths to intermediate data files.
        intermediateFilesDirectory = os.path.join(metadata.directory,"intermediate_files")
        
        bedExpansionFilePath = generateFilePath(directory = intermediateFilesDirectory, dataGroup = metadata.dataGroupName,
                                                dataType = "intermediate_expansion", fileExtension = ".bed")

        fastaReadsFilePath = generateFilePath(directory = intermediateFilesDirectory, dataGroup = metadata.dataGroupName,
                                              dataType = "expanded_reads", fileExtension = ".fa")

        # Generate a path to the final output file.
        expandedContextFilePath = generateFilePath(directory = metadata.directory, dataGroup = metadata.dataGroupName,
                                                  context = contextText, dataType = DataTypeStr.mutations, fileExtension = ".bed")

        # Create a directory for intermediate files if it does not already exist...
        if not os.path.exists(intermediateFilesDirectory):
            os.mkdir(os.path.join(intermediateFilesDirectory))

        # Expand the nucleotide coordinates in the singlenuc context bed file as requested.
        expandBedPositions(inputBedFilePath,bedExpansionFilePath,expansionContextNum)

        # Convert the expanded coordinates in the bed file to the referenced nucleotides in fasta format.
        bedToFasta(bedExpansionFilePath,metadata.genomeFilePath,fastaReadsFilePath)

        # Using the newly generated fasta file, create a new bed file with the expanded context.
        generateExpandedContext(inputBedFilePath,fastaReadsFilePath,expandedContextFilePath,expansionContextNum)

        expandedContextFilePaths.append(expandedContextFilePath)

        # Delete the input file, which has the same mutation information, but a smaller context.
        print("Deleting old mutation context file...")
        os.remove(inputBedFilePath)

    return expandedContextFilePaths


def main():

    # Create the Tkinter dialog.
    dialog = TkinterDialog(workingDirectory=getDataDirectory())
    dialog.createLabel("Note: Either single-base or trinuc context bed files will suffice.  Both are not necessary.",0,0,2)
    dialog.createMultipleFileSelector("Single-Base Bed File:",1,"singlenuc_" + DataTypeStr.mutations + ".bed",("Bed Files",".bed"))
    dialog.createMultipleFileSelector("Trinuc Context Bed File:",2,"trinuc_" + DataTypeStr.mutations + ".bed",("Bed Files",".bed"))
    dialog.createDropdown("Expansion Context",3,0,("Trinuc", "Pentanuc"))

    # Run the UI
    dialog.mainloop()

    # If no input was received (i.e. the UI was terminated prematurely), then quit!
    if dialog.selections is None: quit()

    # Get the user's input from the dialog.
    selections: Selections = dialog.selections
    inputBedFilePaths = list(selections.getFilePathGroups())[0] # A list of paths to original bed mutation files
    trinucContextBedFilePaths = list(selections.getFilePathGroups())[1] # A list of paths to trinuc context bed mutation files
    expansionContext = list(selections.getDropdownSelections())[0] # What context the file should be expanded to.

    if expansionContext == "Trinuc":
        expansionContextNum = 3
    elif expansionContext == "Pentanuc":
        expansionContextNum = 5
    else: raise ValueError("Matching strings is hard.")

    expandContext(inputBedFilePaths + trinucContextBedFilePaths, expansionContextNum)

if __name__ == "__main__": main()
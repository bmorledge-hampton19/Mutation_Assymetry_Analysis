# This script, when given a mutation background file, a genome file, and a file of strongly positioned nucleosome coordinates,
# generates a background file with the expected mutations at each dyad position from -73 to 73 (inclusive).

from TkinterDialog import TkinterDialog, Selections
import os, subprocess
from typing import Dict
from UsefulBioinformaticsFunctions import bedToFasta, reverseCompliment, FastaFileIterator
from UsefulFileSystemFunctions import getContext, getLinkerOffset, Metadata, generateFilePath, dataTypes


# This function takes a bed file of strongly positioned nucleosomes and expands their coordinates to encompass
# 75 bases on either side of the dyad. (in order to get up to pentanucleotide sequences for positions -73 to 73)
# If a linker offset is requested, the expansion will be even greater to accomodate.
# The expanded bed file is then used to generate a fasta file of nucleosome sequences.
# Returns the file path to the fasta file.
def generateStrongPosNucleosomeFasta(baseNucPosFilePath, genomeFilePath, linkerOffset):

    # Generate a path to the fasta file of strongly positioned nucleosome sequences (Potentially including linker DNA).
    nucPosFastaFilePath = generateFilePath(directory = os.path.dirname(baseNucPosFilePath),
                                           dataGroup = os.path.basename(baseNucPosFilePath).rsplit('.',1)[0],
                                           linkerOffset = linkerOffset,
                                           fileExtension = ".fa") 

    # Make sure the file doesn't already exist.  If it does, we're done!
    if os.path.exists(nucPosFastaFilePath):
        print("Found relevant nucleosome fasta file:",os.path.basename(nucPosFastaFilePath))
        return nucPosFastaFilePath
    else: print("Nucleosome fasta file not found at: ",nucPosFastaFilePath,"\nGenerating...", sep = '')

    # Generate the expanded file path.
    expandedNucPosBedFilePath = generateFilePath(directory = os.path.dirname(baseNucPosFilePath),
                                                 dataGroup = os.path.basename(baseNucPosFilePath).rsplit('.',1)[0],
                                                 linkerOffset = linkerOffset, dataType = "expanded", fileExtension = ".bed")

    # Expand the bed coordinates.
    print("Expanding nucleosome coordinates...")
    with open(baseNucPosFilePath,'r') as baseNucPosFile:
        with open(expandedNucPosBedFilePath, 'w') as expandedNucPosBedFile:

            # Write the expanded positions to the new file, one line at a time.
            for line in baseNucPosFile:
                choppedUpLine = line.strip().split('\t')
                choppedUpLine[1] = str(int(choppedUpLine[1]) - 75 - linkerOffset)
                choppedUpLine[2] = str(int(choppedUpLine[2]) + 75 + linkerOffset)

                # Write the results to the expansion file as long as it is not before the start of the chromosome.
                if int(choppedUpLine[1]) > -1: expandedNucPosBedFile.write('\t'.join(choppedUpLine) + '\n')
                else: print("Nucleosome at chromosome", choppedUpLine[0], "with expanded start pos", choppedUpLine[1],
                            "extends into invalid positions.  Skipping.")
                                            
    # Convert the expanded bed file to fasta format.
    print("Converting expanded coordinates to fasta file...")
    bedToFasta(expandedNucPosBedFilePath,genomeFilePath,nucPosFastaFilePath, includeStrand=False)

    return nucPosFastaFilePath


# Returns a dictionary of background mutation rates for the relevant contexts in the associated genome.
def getGenomeBackgroundMutationRates(genomeMutationBackgroundFilePath):

    genomeBackgroundMutationRates = dict()

    # Open the file and read the lines into the dictionary.
    with open(genomeMutationBackgroundFilePath, 'r') as genomeMutationBackgroundFile:
        genomeMutationBackgroundFile.readline() # Skip the line with headers.
        for line in genomeMutationBackgroundFile:
            choppedUpLine = line.strip().split('\t')
            genomeBackgroundMutationRates[choppedUpLine[0]] = float(choppedUpLine[1])
    
    return genomeBackgroundMutationRates


# This function generates a file of context counts in the genome for each dyad position.
def generateDyadPosContextCounts(nucPosFastaFilePath, dyadPosContextCountsFilePath, 
                                 contextNum, linkerOffset):

    # Dictionary of context counts for every dyad position. (Contains a dictionary of either counts for each dyad position)
    plusStrandNucleosomeDyadPosContextCounts = dict()

    observedContexts = dict() # Hash table of observed contexts for lookup.

    # Initialize the dictionary for context counts on the plus strand.
    for dyadPos in range(-73-linkerOffset,74+linkerOffset): 
        plusStrandNucleosomeDyadPosContextCounts[dyadPos] = dict()

    # Read through the file, adding contexts for every dyad position to the running total in the dictionary
    with open(nucPosFastaFilePath, 'r') as nucPosFastaFile:

        trackedPositionNum = 73*2 + 1 + linkerOffset*2 # How many dyad positions we care about.

        for fastaEntry in FastaFileIterator(nucPosFastaFile):

            # Reset dyad position counter
            dyadPos = -73 - linkerOffset
            
            # Determine how much extra information is present in this line at either end for generating contexts.
            extraContextNum = len(fastaEntry.sequence) - trackedPositionNum

            # Make sure we have an even number before dividing by 2 (for both ends)
            if extraContextNum%2 != 0:
                raise ValueError(str(extraContextNum) + " should be even.")
            else: extraContextNum = int(extraContextNum/2)


            # Used to pull out the context of desired length.
            extensionLength = int(contextNum/2)

            # Count all available contexts.
            for i in range(0,trackedPositionNum):

                context = fastaEntry.sequence[i+extraContextNum - extensionLength:i + extraContextNum + extensionLength+1]
                if len(context) != contextNum: raise ValueError("Sequence length does not match expected context length.")
                if context not in observedContexts: observedContexts[context] = None              
                plusStrandNucleosomeDyadPosContextCounts[dyadPos][context] = plusStrandNucleosomeDyadPosContextCounts[dyadPos].setdefault(context, 0) + 1

                # Increment the dyadPos counter
                dyadPos += 1

    # Write the context counts for every dyad position on the plus strand in the output file
    with open(dyadPosContextCountsFilePath, 'w') as dyadPosContextCountsFile:

        # Write the header for the file
        dyadPosContextCountsFile.write("Dyad_Pos\t" + '\t'.join(observedContexts.keys()) + '\n')

        # Write the context counts at each dyad position.
        for dyadPos in plusStrandNucleosomeDyadPosContextCounts.keys():
            
            dyadPosContextCountsFile.write(str(dyadPos))

            for context in observedContexts.keys():
                if context in plusStrandNucleosomeDyadPosContextCounts[dyadPos]:
                    dyadPosContextCountsFile.write('\t' + str(plusStrandNucleosomeDyadPosContextCounts[dyadPos][context]))
                else: dyadPosContextCountsFile.write('\t0')

            dyadPosContextCountsFile.write('\n')
        
    
# This function retrieves the context counts for each dyad position in a genome from a given file.
# The data is returned as a dictionary of dictionaries, with the first key being dyad position and the second
# being a context.
def getDyadPosContextCounts(dyadPosContextCountsFilePath):
    with open(dyadPosContextCountsFilePath, 'r') as dyadPosContextCountsFile:
        
        contexts = list()
        headersHaveBeenRead = False
        dyadPosContextCounts= dict()

        for line in dyadPosContextCountsFile:

            if not headersHaveBeenRead:
                headersHaveBeenRead = True
                contexts = line.strip().split('\t')[1:]
    
            else: 
                choppedUpLine = line.strip().split('\t')
                dyadPos = int(choppedUpLine[0])
                dyadPosContextCounts[dyadPos] = dict()
                for i,context in enumerate(contexts):
                    dyadPosContextCounts[dyadPos][context] = int(choppedUpLine[i+1])

    return dyadPosContextCounts


# This function generates a nucleosome mutation background file from a general mutation background file
# and a file of strongly positioned nucleosome coordinates.
def generateNucleosomeMutationBackgroundFile(dyadPosContextCountsFilePath, mutationBackgroundFilePath, 
                                             nucleosomeMutationBackgroundFilePath, linkerOffset):
    print("Generating nucleosome mutation background file...")

    # Dictionaries of expected mutations for every dyad position included in the analysis, one for each strand.
    plusStrandNucleosomeMutationBackground = dict() 
    minusStrandNucleosomeMutationBackground = dict()

    # Initialize the dictionary
    for dyadPos in range(-73-linkerOffset,74+linkerOffset): 
        plusStrandNucleosomeMutationBackground[dyadPos] = 0
        minusStrandNucleosomeMutationBackground[dyadPos] = 0

    # Get the corresponding mutation background and context counts dictionaries.
    backgroundMutationRate = getGenomeBackgroundMutationRates(mutationBackgroundFilePath)
    dyadPosContextCounts = getDyadPosContextCounts(dyadPosContextCountsFilePath)

    # Calculate the expected mutation rates for each dyad position based on the context counts at that position and that context's mutation rate
    for dyadPos in dyadPosContextCounts:

        for context in dyadPosContextCounts[dyadPos]:

            reverseContext = reverseCompliment(context)
            
            # Add the context's mutation rate to the running total in the background dictionaries.
            plusStrandNucleosomeMutationBackground[dyadPos] += backgroundMutationRate[context] * dyadPosContextCounts[dyadPos][context]
            minusStrandNucleosomeMutationBackground[dyadPos] += backgroundMutationRate[reverseContext] * dyadPosContextCounts[dyadPos][context]

    # Write the results of the dictionary to the nucleosome mutation background file.
    with open(nucleosomeMutationBackgroundFilePath, 'w') as nucleosomeMutationBackgroundFile:

        # Write the headers for the data.
        headers = '\t'.join(("Dyad_Position","Expected_Mutations_Plus_Strand",
        "Expected_Mutations_Minus_Strand","Expected_Mutations_Both_Strands"))

        nucleosomeMutationBackgroundFile.write(headers + '\n')
        
        # Write the data for each dyad position.
        for dyadPos in range(-73-linkerOffset,74+linkerOffset):

            dataRow = '\t'.join((str(dyadPos),str(plusStrandNucleosomeMutationBackground[dyadPos]),
            str(minusStrandNucleosomeMutationBackground[dyadPos]),
            str(plusStrandNucleosomeMutationBackground[dyadPos] + minusStrandNucleosomeMutationBackground[dyadPos])))

            nucleosomeMutationBackgroundFile.write(dataRow + '\n')


def generateNucleosomeMutationBackground(mutationBackgroundFilePaths, linkerOffset):

    # Whitespace for readability
    print()

    nucleosomeMutationBackgroundFilePaths = list() # A list of paths to the output files generated by the function

    # Loop through each given mutation background file path, creating a corresponding nucleosome mutation background for each.
    for mutationBackgroundFilePath in mutationBackgroundFilePaths:

        # Get metadata
        metadata = Metadata(mutationBackgroundFilePath)

        # Make sure we have a fasta file for strongly positioned nucleosome coordinates
        nucPosFastaFilePath = generateStrongPosNucleosomeFasta(metadata.baseNucPosFilePath, metadata.genomeFilePath, linkerOffset)

        mutationBackgroundFileName = os.path.split(mutationBackgroundFilePath)[1]
        print("\nWorking with file:",mutationBackgroundFileName)
        if not dataTypes.mutBackground in mutationBackgroundFileName: 
            raise ValueError("Error, expected file with \"" + dataTypes.mutBackground + "\" in the name.")

        # Determine the context of the mutation background file
        contextNum = getContext(mutationBackgroundFilePath, asInt=True)
        contextText = getContext(mutationBackgroundFilePath)

        print("Given mutation background is in", contextText, "context.")

        # Generate the path to the tsv file of dyad position context counts
        dyadPosContextCountsFilePath = generateFilePath(directory = os.path.dirname(metadata.baseNucPosFilePath),
                                                        dataGroup = metadata.nucPosName,
                                                        context = contextText, linkerOffset = linkerOffset,
                                                        dataType = "dyad_pos_counts", fileExtension = ".tsv")

        # Make sure we have a tsv file with the appropriate context counts at each dyad position.
        if not os.path.exists(dyadPosContextCountsFilePath): 
            print("Dyad position " + contextText + " counts file not found at",dyadPosContextCountsFilePath)
            print("Generating genome wide dyad position " + contextText + " counts file...")
            generateDyadPosContextCounts(nucPosFastaFilePath, dyadPosContextCountsFilePath,
                                         contextNum, linkerOffset)

        # A path to the final output file.
        nucleosomeMutationBackgroundFilePath = generateFilePath(directory = metadata.directory, dataGroup = metadata.dataGroupName,
                                                                context = contextText, linkerOffset = linkerOffset,
                                                                dataType = dataTypes.nucMutBackground, fileExtension = ".tsv")

        # Generate the nucleosome mutation background file!
        generateNucleosomeMutationBackgroundFile(dyadPosContextCountsFilePath,mutationBackgroundFilePath,
                                                 nucleosomeMutationBackgroundFilePath, linkerOffset)

        nucleosomeMutationBackgroundFilePaths.append(nucleosomeMutationBackgroundFilePath)

    return nucleosomeMutationBackgroundFilePaths


if __name__ == "__main__":
    #Create the Tkinter UI
    dialog = TkinterDialog(workingDirectory=os.path.join(os.path.dirname(__file__),"..","data"))
    dialog.createMultipleFileSelector("Mutation Background Files:",0,dataTypes.mutBackground + ".tsv",("Tab Seperated Values Files",".tsv"))
    dialog.createCheckbox("Include linker DNA",1,0,2)
    dialog.createReturnButton(2,0,2)
    dialog.createQuitButton(2,2,2)

    # Run the UI
    dialog.mainloop()

    # If no input was received (i.e. the UI was terminated prematurely), then quit!
    if dialog.selections is None: quit()

    # Get the user's input from the dialog.
    selections: Selections = dialog.selections
    filePaths = list(selections.getFilePaths())
    mutationBackgroundFilePaths = list(selections.getFilePathGroups())[0] # A list of mutation background file paths
    includeLinker: bool = list(selections.getToggleStates())[0] # Whether or not to include linker DNA on either side of the nucleosomes.
  
    # Set the linker offset.
    if includeLinker: linkerOffset = 30
    else: linkerOffset = 0

    generateNucleosomeMutationBackground(mutationBackgroundFilePaths, linkerOffset)
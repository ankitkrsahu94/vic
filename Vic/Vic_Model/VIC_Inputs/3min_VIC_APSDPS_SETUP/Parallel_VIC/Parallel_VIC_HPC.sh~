#!/bin/bash
#############################################################################################################
# This bash scripting perform parallel execution of VIC Model. Execution of this file depends upon the      #
# configuration file.                                                                                       #
# Way of Execution: $ ./Parallel_VIC.sh Parallel_VIC_Conf.cgf                                               #
# After Successful Execution: Output generate based on the output location configuration in global_parameter#              
# file.                                                                                                     #
# Designed by: ASD&CIG, RSA-A, NRSC, ISRO                                                                   #
# Author: Anil Yadav & Nitin Mishra                                                                         #
# Date: 16/1/2014                                                                                           #
#############################################################################################################

# Command Line Argument Checking
args=("$@")
if [ $# = 1 ]; then
	if [ `echo $1 | cut -d'.' -f2` = "cfg" ] 
	then 
		echo "File extension correct"
	else
		echo "Wrong configuration file, Please Enter Valid Configuration File!!!!!"
		exit
	fi
else
        echo 'Incorrect Argument:Only one configuration file is require!!!'
        exit
fi
##################################

##get the parameter from configuration file
source $1
#########################################

##start date and time, it is require to calculate execution time of the Parallel VIC Model
date1=$(date +"%s")
##########################################################################################
## count the totla number of lines in soil parameter file
count=$(sed -n '$=' $soil_directory_path$soil_file_name)
echo 'count='$count
## calculate the number of lines in each split file for full code configuration
count_split=$(($count/53))
echo 'count_split='$count_split
##spliting of soil parameter file
cd $soil_directory_path
split -d -l $count_split $soil_directory_path$soil_file_name soil_parameter
#split -d -l 200 $soil_directory_path$soil_file_name soil_parameter
#################################

## Output generation for each spilited part of soil paramter file
for i in {00..54}
 do
     ## Replacing of 'general soilparameter file' in global_parameter file with 'spilited soil paramteter file' 
     _r1="$soil_directory_path$soil_file_name"
     _r2="$soil_directory_path""soil_parameter$i"
      ## Escape path for sed using bash find and replace 
      _r1="${_r1//\//\\/}"
      _r2="${_r2//\//\\/}"
      # replace soil parmeter path in global file
      global_out="$global_directory_path$global_file_name"_$i
      sed -e "s/${_r1}/${_r2}/" $global_directory_path$global_file_name > $global_out

     # Condition is true for 0-9 file
     if [ $i -lt 10 ]
     then
         echo 'first node'
 	  ssh vic@node01 $vic_executable_path -g $global_out &

     # Condition is true for 10-19th file
     elif [ $i -gt 9 ] && [ $i -lt 20 ]
     then
        echo 'second node'
	ssh vic@node02 $vic_executable_path -g $global_out &

     # Condition is true for 20-29th file
     elif [ $i -gt 19 ] && [ $i -lt 30 ]
     then
        echo 'third node' 
 	ssh vic@node03 $vic_executable_path -g $global_out &

     # Condition is true for 30-39th file.
     elif [ $i -gt 29 ] && [ $i -lt 40 ]
     then
         echo 'fourth node'
	 ssh vic@node04 $vic_executable_path -g $global_out &

     # Condition is true for 40-49th file    
     elif [ $i -gt 39 ] && [ $i -lt 50 ]
     then
         echo 'fifth node'
	 ssh vic@node05 $vic_executable_path -g $global_out &

     # Condition is true for 50-59th file.
     elif [ $i -gt 49 ] && [ $i -lt 60 ]
     then
         echo 'sixth node'
	 ssh vic@node06 $vic_executable_path -g $global_out &

     # Condition is true for 60-69th file
     elif [ $i -gt 59 ] && [ $i -lt 70 ]
     then
         echo 'seventh node'
	 ssh vic@node07 $vic_executable_path -g $global_out &

     # Condition is true for 70-79th file
     elif [ $i -gt 69 ] && [ $i -lt 80 ]
     then
         echo 'eighth node'
	 ssh vic@node08 $vic_executable_path -g $global_out &
     fi
done
##################################################################################

## Wait Untill all processes isn't completed
wait
############################################

## delete splitted soil files and global files
 rm $soil_directory_path""soil_parameter*
 rm $global_directory_path$global_file_name""_*

##End Date&Time : It Is require to calculate total amount of time during execution of Parallel VIC Model
date2=$(date +"%s")
########################################################################################################

# Calculation of total amount of time during execution of Parallel VIC Model
diff=$(($date2-$date1))
############################################################################

# Finished
echo "-------------------------------------------------------------------------------------------------------------"
echo "-------------------------------------------------------------------------------------------------------------"
echo "--------------------Execution of Parallel VIC Model Finished!!!!!!!!-----------------------------------------"
echo " "
echo "***Total time of execution for Parallel VIC Model is: $(($diff / 60)) minutes and $(($diff % 60)) seconds  "
echo "-------------------------------------------------------------------------------------------------------------"
echo " "
echo " "
#################################------End------##################################################################

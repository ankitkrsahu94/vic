#!/bin/bash
clear
DIRVAR="/home/saksham/Desktop/VIC/9min_Ind"
mrDate=$(date +"%Y%m%d" -d "-2days")
GEFSDate=$(date +"%d" -d "+5days")
GEFSMonth=$(date +"%m" -d "+5days")
GEFSYear=$(date +"%Y" -d "+5days")
SMDate=$(date +"%d" -d "-2days")
SMMonth=$(date +"%m" -d "-2days")
SMYear=$(date +"%Y" -d "-2days")
text=("flux_20130501-")

cd $DIRVAR
mkdir -p "${DIRVAR}/${text}${mrDate}"
suffix="param.India_4p"

echo "Modifying Global Parameter File For Current Day Run.."

find . -maxdepth 1 -type f -name "*${suffix}" -exec sed -i "s/\(ENDMONTH\s*\)[0-9]*\(.*\)$/\1${GEFSMonth}\2/" {} +
find . -maxdepth 1 -type f -name "*${suffix}" -exec sed -i "s/\(ENDDAY\s*\)[0-9]*\(.*\)/\1${GEFSDate}\2/" {} +
find . -maxdepth 1 -type f -name "*${suffix}" -exec sed -i "s/\(ENDYEAR\s*\)[0-9]*\(.*\)/\1${GEFSYear}\2/" {} +

find . -maxdepth 1 -type f -name "*${suffix}" -exec sed -i "s/\(STATEMONTH\s*\)[0-9]*\(.*\)/\1${SMMonth}\2/" {} +
find . -maxdepth 1 -type f -name "*${suffix}" -exec sed -i "s/\(STATEDAY\s*\)[0-9]*\(.*\)/\1${SMDate}\2/" {} +
find . -maxdepth 1 -type f -name "*${suffix}" -exec sed -i "s/\(STATEYEAR\s*\)[0-9]*\(.*\)/\1${SMYear}\2/" {} +

find . -maxdepth 1 -type f -name "*${suffix}" -exec sed -i "s/\(RESULT_DIR.*flux_[0-9]*\-\)[0-9]*\(.*\)/\1${mrDate}\2/" {} +
find . -maxdepth 1 -type f -name "*${suffix}" -exec sed -i "s/\(FORCING1.*Files_[0-9]*\-\)[0-9]*\(.*\)/\1${mrDate}\2/" {} +

file=($(find . -maxdepth 1 -type f -name "*${suffix}"))
echo "done.."
echo "*********** Executing Model Run ***********"
for i in "${file[@]}"
do
	vicNl -g "${i}"
	
done
echo "*********** Model Run Completed ***********"

cd ${DIRVAR}/${text}${mrDate}
rm snow*

echo "*********** Initializing Routing Module ***********"

DIRVAR="/home/saksham/Desktop/VIC/9min_rout"
#vicdir="/home/karthik/flux_20130101-20140101.vic"
newDate=$(date +"%Y%m%d" -d "-2days")
prevYear=$(date +"%Y" -d "-1year")
curYear=$(date +"%Y")
prevMonth=$(date +"%m" -d "-1month")
logdate=$(date +"%Y%m%d")
log="log"
logfile="$logdate$log"
cd $DIRVAR

find . -type f -name "*_rout" -exec sed -i "s/\(.*flux_\)\([0-9]*\)\-[0-9]*\(.*\)/\1\2-${newDate}\3/" {} +
#find . -type f -name "*_rout" -exec sed -i "s/\([0-9]*\s[0-9]*\s[0-9]*\)\s\[0-9]*/\1\s${curMonth}/" {} +
find . -type f -name "*_rout" -exec sed -i "s/\(${prevYear}\s[0-9]*\s${curYear}\s\)[0-9]*/\1${prevMonth}/" {} +
#suffix="_rout"
files=( $(find . -type f -name "*_rout"))
echo "Routing Inprocess..."
{
for i in "${files[@]}"
do
	rout "${i}"
	
done
} > $logfile
echo "Routing Completed.."
echo "Check log file for any errors.."

out1=".day"
out2=".day_mm"

outDir="/home/saksham/Desktop/VIC/9min_rout/allbasin_rout_output"

echo "Copying output files to output directory.."
find . -regex ".*/.*/.*out/.[^/]*${out1}" -exec cp -ft "${outDir}" {} +
find . -regex ".*/.*/.*out/.[^/]*${out2}" -exec cp -ft "${outDir}" {} +
echo "Done.."
echo "Check Rout Files in /home/saksham/Desktop/VIC/9min_rout/allbasin_rout_output.."

echo "*********** Initializing Matlab Computations ***********"
cd /home/saksham/Matlab_programs/executables
./run_master_v1.sh /home/saksham/MATLAB/MATLAB_Compiler_Runtime/v717/

#delete folder
DIRVAR="/home/saksham/Desktop/VIC/9min_Ind"
delfolDate=$(date +"%Y%m%d" -d "-6days")
cd ${DIRVAR}/${text}${delfolDate}
rm flux*
rm VIC*
cd $DIRVAR
rmdir -p "${DIRVAR}/${text}${delfolDate}"

text2=("IP_Met_Files_20130501-")
cd ${DIRVAR}/${text2}${delfolDate}
rm data*
cd $DIRVAR
rmdir -p "${DIRVAR}/${text2}${delfolDate}"


#move nc file to desktop
DIRVAR="/home/saksham/Desktop/VIC/9min_Ind"
cd ${DIRVAR}/${text}${mrDate}
mv *.nc /home/saksham/Desktop/

# copy bhuvan input files to desktop



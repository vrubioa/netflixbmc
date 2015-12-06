DATA_DIR=$1
mkdir tmp
cd tmp
TEMP_DIR=chrome-user-data

rm -rf $TEMP_DIR
mkdir -p $TEMP_DIR/Default

cp -a $DATA_DIR/WidevineCDM $DATA_DIR/First\ Run $TEMP_DIR
cp -a \
$DATA_DIR/Default/Cookies \
$DATA_DIR/Default/Extensions \
$DATA_DIR/Default/Preferences \
$DATA_DIR/Default/Secure\ Preferences \
$TEMP_DIR/Default/

rm -rf chrome-user-data.zip
zip -r -9 chrome-user-data.zip $TEMP_DIR/
mv chrome-user-data.zip ../

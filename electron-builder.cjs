'use strict';
module.exports={
 appId:'org.chartmate.desktop',productName:'ChartMate',
 directories:{output:'dist',buildResources:'build'},
 files:['desktop/**/*','package.json'],asar:true,
 extraResources:[{from:'runtime',to:'runtime'},{from:'THIRD_PARTY.md',to:'THIRD_PARTY.md'}],
 win:{target:[{target:'nsis',arch:['x64']}],requestedExecutionLevel:'asInvoker',artifactName:'ChartMate-Setup-${version}-win-${arch}.${ext}'},
 nsis:{oneClick:false,perMachine:true,allowToChangeInstallationDirectory:true,createDesktopShortcut:true,createStartMenuShortcut:true,shortcutName:'ChartMate',deleteAppDataOnUninstall:false,include:'build/installer.nsh'}
};

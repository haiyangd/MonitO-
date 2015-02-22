$(document).ready(function () {
    setInterval(function () {
      $("#load_chart").load('/data/192.168.1.1?graph=load'); 
      $("#mem_chart").load('/data/192.168.1.1?graph=mem'); 
    }, 10000);
});
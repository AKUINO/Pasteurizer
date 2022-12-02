var gradient = ["FF0000","FF0A00","FF1400","FF1E00","FF2800","FF3200","FF3C00","FF4600","FF5000","FF5A00","FF6400","FF6E00","FF7800","FF8200","FF8C00","FF9600","FFA000","FFAA00","FFB400","FFBE00","FFC800","FFD200","FFDC00","FFE600","FFF000","FFFA00","FDFF00","D7FF00","B0FF00","8AFF00","65FF00","3EFF00","17FF00","00FF10","00FF36","00FF5C","00FF83","00FFA8","00FFD0","00FFF4","00E4FF","00D4FF","00C4FF","00B4FF","00A4FF","0094FF","0084FF","0074FF","0064FF","0054FF","0044FF","0032FF","0022FF","0012FF","0002FF","0000FF"
];
var milieu = 32

function float(value) {
    if (value == '') return 0.0;
    else return (value+0.0);
}

function color(value,mini,typi,maxi) {
    var pos = milieu
    if (value < typi) {
        if (value <= mini) {
            pos = gradient.length-1;
        } else {
            pos = milieu + ~~ ( (typi-value) * (gradient.length-milieu) / (typi-mini) )
        }
    } else if (value > typi) {
        if (value >= maxi) {
            pos = 0;
        } else {
            pos = ~~ ( (maxi - value) * float(milieu) / (maxi - typi) )
        }
    }
    return gradient[pos]
}

function textcolor(red, green, blue) {
    var total =( (0.299*parseInt(red,16))+(0.587*parseInt(green,16))+(0.114*parseInt(blue,16)) ) / 255.0
    //console.log(red+'.'+green+'.'+blue+", luminance="+total.toString());
    if (total > 0.5) return "000000"; //357
    else return "EEEEEE";
}

function colorit(cell,mini,typi,maxi) {
    value = parseFloat(cell.text());
    if (value == 0.0) {
        return 'white'
    }
    var col = color(value,mini,typi,maxi);
    var txcol = textcolor(col.substring(0,2),col.substring(2,4),col.substring(4,6));
    //cell.css("background-color",col);
    cell.parent().css("background-color",'#'+col);
    cell.parent().css("color",'#'+txcol);
    cell.parent().css("border-color",'#000000');
    return col
}

function floorUni(tx) {
    return (~~parseFloat(tx)).toString()
}

function floorUni2(tx,tx2) {
    return (~~(parseFloat(tx)+parseFloat(tx2))).toString()
}

function floorDeci(tx) {
    return ((~~(parseFloat(tx)*10.0)) / 10.0).toString()
}

function floorCenti(tx) {
    return ((~~(parseFloat(tx)*100.0)) / 100.0).toString()
}

function floorCenti2(tx,tx2) {
    return ((~~((parseFloat(tx)+parseFloat(tx2))*100.0)) / 100.0).toString()
}

var allowedActions = '';
var currentLetter = '';

function goToLetter(pageLetter,letter,PleaseClick) {
    if (pageLetter == letter) {
        location.reload();
        $('#drop'+letter).attr("href", "#doc");
        console.log("/explain/"+letter+"#doc (reload)")
    } else {
        $('.navbar-collapse').collapse('hide');
        $('#confirm').hide();
        $('#cancel').hide();
        console.log("/explain/"+letter+"#doc");
        window.location.href = "/explain/"+letter+"#doc";
    }
    currentLetter = letter;
}

function fromHereTo(pageLetter,letter) {
    if (allowedActions.indexOf(letter) >= 0) {
        goToLetter(pageLetter,letter,false);
        return true;
    } else {
        $('.pageLetter').text(pageLetter);
        $('.currLetter').text(letter);
        var myModal = new bootstrap.Modal(document.getElementById('ModalConfirm'), {
          keyboard: false, focus: true
        });
        $('#ModalConfirmContinue').click ( function() {
          console.log(letter+" confirmed.");
          myModal.hide();
          goToLetter(pageLetter,letter,true);
        } );
        myModal.show();
        console.log(myModal);
        return false;
    }
}

var ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

function SVGready(elements) {
    elements.each( function() { var here = $(this); here.removeClass(); SVGready(here.children()) } );
}

$(document).ready(function() {
    var logging = ($("#tableau").length > 0);
    if (logging) {
        var t = $('#tableau').DataTable( {
            "ajax": "/api/log",
            "order": [[ 0, "desc" ]],
            "ordering":       true,
            "searching":      false,
            "scrollX":        true,
            "scrollY":        "150px",
            "scrollCollapse": true,
            "paging":         false,
            "info":           false,
            "columnDefs": [
                {
                    targets: -1,
                    className: 'dt-body-right'
                }
            ]
        } ).draw();
    }

    setInterval ( function() {
        $.ajax({
        url: "/api/log",
        cache: false,
        error: function (jqXHR, textStatus, errorThrown ) {
            $('#message').text('Application '+(textStatus?textStatus:'')+(errorThrown?(' '+errorThrown):''));
        },
        timeout: 3000, // sets timeout to 3 seconds
        success: function(data) {
                if (data && 'date' in data) {
                    var date = data['date'].substring(0,10);
                    $('[name=date]').text(date);
                    var time = data['date'].substring(11,999);
                    $('#time').text(time);
                    $('#actionletter').text(data['actionletter']);
                    currentLetter = data['actionletter'];
                    $('#preconfigletter').text(data['preconfigletter']);
                    $('#action').text(data['action']);
                    $('#stateletter').text(data['stateletter']);
                    $('#state').text(data['state']);
                    $('.show-flow').css('color',data['statecolor']);
                    $('#empty').text(data['empty']);
                    //$('#level1').text(data['level1']); //linput
                    //$('#level2').text(data['level2']); //loutput
                    if (data[level1]=='0') {
                        $('#level1').show()
                    } else {
                        $('#level1').hide()
                    }
                    if (data[level2]=='1') {
                        $('#level2').show()
                    } else {
                        $('#level2').hide()
                    }
                    // $('#greasy').text(data['greasy']);
                    $('#actiontitle').text(data['actiontitle']);
                    var accro = "";
                    if ('accro' in data && data['accro'].length >= 4) {
                        accro = data['accro'].substring(3,4)
                    }
                    $('#accro').text(accro);
                    //$('#totalwatt').text(floorUni2(data['totalwatts'],data['totalwatts2']));
                    $('#totalwatt').text(floorUni(data['totalwatts']));
                    $('#watts').text(floorUni(data['watts']));
                    //$('#watts2').text(floorUni(data['watts2']));
                    $('#volume').text(floorDeci(data['volume']));
                    if ('remain' in data && data['remain']) {
                        $('#remain').html('&blacktriangledown;<b>'+floorDeci(data['remain'])+'</b>L');
                    } else {
                        $('#remain').html('');
                    }
                    if ('delay' in data && data['delay'] != '') {
                        $('#delay').html('&blacktriangledown;<b>'+data['delay']+'</b>"');
                    } else {
                        $('#delay').html('');
                    }
                    if ('fill' in data && data['fill']>0) {
                        $('#fill').show();
                    } else {
                        $('#fill').hide();
                    }
                    var speed = floorUni(data['speed']);
                    $('#vitesse').text(speed);
                    colorit($('#vitesse'),0.0,625*3.6/data['opt_M'],180.0);
                    $('#input').text(floorDeci(data['input']));
                    $('#intake').text(floorDeci(data['intake']));
                    $('#warranty').text(floorDeci(data['warranty']));
                    colorit($('#sp9'),45.0,data['opt_temp'],90.0);
                    $('#reft').text(floorDeci(data['reft']));
                    $('#heating').text(floorDeci(data['heating']));
                    colorit($('#heating'),45.0,data['opt_temp']+3,90.0);
                    //$('#temper').text(floorDeci(data['temper']));
                    //colorit($('#temper'),4.0,(data['watts2'] <= 0) ? data['opt_T'] : data['opt_temp'],70.0);
                    $('#rmeter').text(data['rmeter'] > 0.0 ? (floorUni(data['rmeter'])+'u') : "");
                    $('#press').text(data['press'] > 0.0 ? floorCenti(data['press']) : "?");
                    $('#pressMin').text(data['pressMin'] > 0.0 ? floorCenti(data['pressMin']) : "?");
                    $('#pressMax').text(data['pressMax'] > 0.0 ? floorCenti(data['pressMax']) : "?");
                    $('#extra').text(data['extra'] != 0.0 ? (floorDeci(data['extra'])+'°'):"");
                    $('#pumpeff').text(floorDeci(data['pumpeff']));
                    $('#heateff').text(floorDeci(data['heateff']));
                    $('#message').text(data['message']);
                    if (data['allowedActions'] != '') {
                        //console.log('AA='+data['allowedActions']);
                        allowedActions = data['allowedActions']+'JYLTOXZ';
                        for (var i=0; i < ALPHABET.length; i++) {
                            ml = ALPHABET.charAt(i);
                            if (ml == data['actionletter']) {
                                //console.log('current='+
                                $('#drop'+ml).removeClass('dropdown-grayed').addClass('current').removeClass('enabled');
                                //$('#menu'+ml).removeClass('disabled').addClass('current').removeClass('enabled');
                            }
                            else if (allowedActions.indexOf(ml) >= 0) {
                                //console.log('enable='+
                                $('#drop'+ml).removeClass('dropdown-grayed').removeClass('current').addClass('enabled');
                                //$('#menu'+ml).removeClass('disabled').removeClass('current').addClass('enabled');
                            }
                            else {
                                //console.log('disable='+
                                $('#drop'+ml).addClass('dropdown-grayed').removeClass('current').removeClass('enabled');
                                //$('#menu'+ml).addClass('disabled').removeClass('current').removeClass('enabled');
                            }
                        }
                    } else {
                        //console.log('no AA');
                        allowedActions = 'JYLTOXZ';
                        for (var i=0; i < ALPHABET.length; i++) {
                            ml = ALPHABET.charAt(i);
                            $('#drop'+ml).removeClass('dropdown-grayed').removeClass('current').addClass('enabled');
                            //$('#menu'+ml).removeClass('disabled').removeClass('current').addClass('enabled');
                        }
                    }
                    if (data['actif'] > 0) {
                        $('#STOP').show();
                        if (data['pause'] > 0) {
                            $('#pause').hide();
                            $('#restart').show();
                            $('#force').hide()
                        } else {
                            $('#pause').show();
                            if (data['purge'] > 2) {
                                $('#restart').show();
                                $('#force').hide()
                            }
                            else {
                                $('#restart').hide();
                                $('#force').show()
                            }
                        }
                    } else {
                        $('#STOP').hide();
                        $('#pause').hide();
                        $('#restart').hide();
                        $('#force').hide()
                    }
                    if (data['actif'] > 0 && data['added'] == 1) {
                        if (data['pause'] > 0) {
                            $('#addbutton').hide();
                        } else {
                            $('#addbutton').show().addClass("btn-success").removeClass("btn-light").removeClass("disabled");
                        }
                    } else if (data['added'] >= 2) {
                        $('#addbutton').show().removeClass("btn-success").addClass("btn-light").addClass("disabled");
                    } else {
                        $('#addbutton').hide();
                    }
                    if (data['purge'] == 1) {
                        //$('#dumpbutton').show();
                        $('#purge').removeClass("glyphicon-trash");
                        $('#purge').removeClass("glyphicon-arrow-left");
                        $('#purge').addClass("glyphicon glyphicon-share-alt flip-vertical")
                    } else if (data['purge'] >= 2) {
                        //$('#dumpbutton').hide();
                        $('#purge').removeClass("glyphicon-arrow-left");
                        $('#purge').removeClass("glyphicon-share-alt");
                        $('#purge').removeClass("flip-vertical");
                        $('#purge').addClass("glyphicon glyphicon-trash")
                    } else {
                        //$('#dumpbutton').hide();
                        $('#purge').removeClass("glyphicon-trash");
                        $('#purge').removeClass("glyphicon-share-alt");
                        $('#purge').removeClass("flip-vertical");
                        $('#purge').addClass("glyphicon glyphicon-arrow-left")
                    }
                    var temptext = ''
                    if ('opt_T' in data && data['opt_T']) {
                        temptext = floorDeci(data['opt_T'])
                        $('#opt_T').text(temptext);
                    }
                    if (temptext.length > 0) {
                        $('#cooling').show();
                    } else{
                        $('#cooling').hide();
                    } 
                    if ('opt_M' in data && data['opt_M']) {
                        $('#opt_M').text(floorDeci(data['opt_M']));
                    }
                    if ('opt_temp' in data && data['opt_temp']) {
                        var temptext = floorDeci(data['opt_temp'])
                        $('#opt_temp').text(temptext);
                        $('#opt_tempbis').text(temptext);
                    }
                    if ('pumpopt' in data && data['pumpopt']) {
                        $('#pumpopt').text(floorDeci(data['pumpopt']));
                    }
                    if (data['pumpeff'] > 0 && speed != 0 ) {
                        $('#eff').show();
                    } else {
                        $('#eff').hide();
                    }
                    if (logging) {
                        tableRow = [time+' '+data['accro'].substring(3,4),
                                    //floorCenti2(data['totalwatts'],data['totalwatts2']), floorCenti2(data['watts'],data['watts2']),
                                    floorCenti(data['totalwatts']), floorCenti(data['watts']),
                                    floorCenti(data['volume']), floorCenti(data['speed']),
                                    floorCenti(data['input']), floorCenti(data['heating']),
                                    floorCenti(data['warranty']), floorCenti(data['intake']),
                                    //floorCenti(data['temper']),
                                    floorCenti(data['extra'])
                        ]
                        t.row.add( tableRow );
                        tableData = t.data();
                        if (tableData.length > 9) { // Keep the total log length reasonable
                            t.row(0).remove()
                        }
                        t.draw(false);
                    }
                }
            }
        });
    }, 3000);   //number of mili seconds between each call
} );

function action(letter) {
   $.ajax({
        url: "/action/"+letter,
        cache: false,
        error: function (jqXHR, textStatus, errorThrown ) {
            $('#message').text('Application '+(textStatus?textStatus:'')+(errorThrown?(' '+errorThrown):''));
        },
        timeout: 3000, // sets timeout to 3 seconds
        success: function(data) {
            if (data) {
                var date = data['date'].substring(0,10);
                $('[name=date]').text(date);
                var time = data['date'].substring(11,999);
                $('#time').text(time);
                $('#actionletter').text(data['actionletter']);
                currentLetter = data['actionletter'];
                $('#preconfigletter').text(data['preconfigletter']);
                $('#action').text(data['action']);
                $('#stateletter').text(data['stateletter']);
                $('#state').text(data['state']);
                $('.show-flow').css('color',data['statecolor']);
                $('#empty').text(data['empty']);
                if (data[level1]=='0') {
                    $('#level1').show()
                } else {
                    $('#level1').hide()
                }
                if (data[level2]=='1') {
                    $('#level2').show()
                } else {
                    $('#level2').hide()
                }
                // $('#greasy').text(data['greasy']);
                $('#actiontitle').text(data['actiontitle']);
                var accro = "";
                if ('accro' in data && data['accro'].length >= 4) {
                    accro = data['accro'].substring(3,4)
                }
                $('#accro').text(accro);
                $('#message').text(data['message']);
                if (data['allowedActions'] != '') {
                    allowedActions = data['allowedActions']+'JYLTOXZ';
                    for (var i=0; i < ALPHABET.length; i++) {
                        ml = ALPHABET.charAt(i);
                        if (allowedActions.indexOf(ml) >= 0) {
                            $('#drop'+ml).removeClass('dropdown-grayed').removeClass('current').addClass('enabled');
                            //$('#menu'+ml).removeClass('disabled').removeClass('current').addClass('enabled');
                        }
                        else {
                            $('#drop'+ml).removeClass('current').removeClass('enabled').addClass('dropdown-grayed');
                            //$('#menu'+ml).addClass('disabled').removeClass('current').removeClass('enabled');
                        }
                    }
                } else {
                    for (var i=0; i < ALPHABET.length; i++) {
                        ml = ALPHABET.charAt(i);
                        $('#drop'+ml).removeClass('dropdown-grayed').removeClass('current').addClass('enabled');
                        //$('#menu'+ml).removeClass('disabled').removeClass('current').addClass('enabled');
                    }
                }
                if (data['pause'] != 0) {
                    $('#pause').hide();
                    $('#restart').show();
                } else {
                    $('#pause').show();
                    $('#restart').hide();
                }
            }
        }
  });
  $('#confirm').hide();
  $('#cancel').hide();
  if (letter == 'Z') {
    $('#documentation').hide();
  }
}


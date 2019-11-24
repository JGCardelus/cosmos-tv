//Global variables
const DEBUG = false;
const startPage = 2;
let allowPageChange = true;

//CONNECT TO SERVER
let socket = null;

function connectServer() {
    //$SOCKET_IP
      socket = io.connect("http://192.168.43.92:8080"); //This line was autogenerated.

    socket.emit('validate_connection');
    socket.on('connection_validated', function() {
        console.log("Connected to server. Welcome back");
    });

}

function loadMDC() {
    $('.button').addClass('mdc-ripple-surface');
    $('.button').attr('data-mdc-auto-init', 'MDCRipple');

    $('.round-button').addClass('mdc-ripple-surface');
    $('.round-button').attr('data-mdc-auto-init', 'MDCRipple');

    $('.fab').addClass('mdc-ripple-surface');
    $('.fab').addClass('mdc-elevation--z6');
    $('.fab').attr('data-mdc-auto-init', 'MDCRipple');

    $('.card').addClass('mdc-elevation--z4');

    $('.mdc-icon-button').attr('data-mdc-auto-init', 'MDCRipple');
    $('.mdc-fab').attr('data-mdc-auto-init', 'MDCRipple');

    mdc.autoInit();
}

function startEnvironment() {
    if (!DEBUG) {
        connectServer();
    }
    loadMDC();
}

startEnvironment();

//PAGE BEHAVIOUR
let windowWidth = $(window).width();
let windowHeight = $(window).height();

$(window).on('resize', function() {
    windowWidth = $(window).width();
    windowHeight = $(window).height();
});

//EVENTS
let eventTriggers = {};
function eventOn(event, callback)
{
    if (!eventTriggers[event])
    {
        eventTriggers[event] = [];
    }
    eventTriggers[event].push(callback);
}

function eventTrigger(event, params)
{
    if (eventTriggers[event])
    {
        for (let trigger of eventTriggers[event])
        {
            trigger(params);
        }
    }
}

//TABS AND POPUPS
let tabs = [];

class Popup
{
    constructor(id, tabs, mainTab)
    {
        this.id = id;
        this.selector = '#' + id;
        this.tabs = tabs;
        this.mainTab = mainTab;

        this.hasChanged = false;

        this.events();
    }

    activate()
    {
        for (let i = 0; i < tabs.length; i++) {
            let tab = tabs[i];
            if (tab != this.tabs) {
                tab.allowPageChange = false;
            }
        }
        this.tabs.allowPageChange = true;
        $(this.selector).css("z-index", "500");
        $(this.selector + " .tabs").css("z-index", "500");
        if ($(this.selector).hasClass("hidden")) {
            $(this.selector).removeClass("hidden");
        }
        this.tabs.change(1);
    }

    deactivate()
    {
        $(this.selector).css("z-index", "0");
        $(this.selector + " .tabs").css("z-index", "0");
        for (let i = 0; i < tabs.length; i++) {
            let tab = tabs[i];
            tab.allowPageChange = false;
        }
        this.mainTab.allowPageChange = true;
        if (!$(this.selector).hasClass("hidden")) {
            $(this.selector).addClass("hidden");
        }
    }

    events()
    {
        this.tabs.on("page-change", () => {
            if (this.tabs.actualTab == 0) {
                if (this.hasChanged) {
                    this.deactivate()
                    this.hasChanged = false;
                }
            } else if (this.tabs.actualTab == 1) {
                this.hasChanged = true;
            }
        });

        $("#close-" + this.id).on("click", () => {
            this.tabs.change(0);
        });
    }
}

//NOTIFICATIONS
const SHORT = 2500;
const LONG = 5000;
let notificationSpan = null;
function startNotification(message, color, emphasis, time)
{
    let nContainer = $('#notification-container');
    hardEndNotification();
    nContainer.css('z-index', '600');
    let notification_html = `<div class="notification side-button">
                    <p class="`+ color +` round-left">` + message +  `</p>
                    <button class="button ` + emphasis + ` fill round-right">
        				<span class="icons">done</span>
        			</button>
        		</div>`

    nContainer.html(notification_html);

    $("#notification-container .button").addClass("mdc-ripple-surface");
    $("#notification-container .button").attr("data-mdc-auto-init", "MDCRipple");

    $("#notification-container .notification").addClass("mdc-elevation--z6");

    mdc.autoInit();

    nContainer.animate({
        bottom: '1.5rem'
    }, 500);

    notificationSpan = setTimeout(function(){
        endNotification();
    }, time);

    $('#notification-container .notification button').click(function()
    {
        endNotification();
    });
}

function hardEndNotification()
{
    clearTimeout(notificationSpan);
    let nContainer = $('#notification-container');
    nContainer.css('bottom', '-4.775rem');
    nContainer.css('z-index', '0');
    nContainer.html("");
}

function endNotification()
{
    clearTimeout(notificationSpan);
    let nContainer = $('#notification-container');
    nContainer.animate({
        bottom: '-4.775rem'
    }, 500, function()
    {
        nContainer.css('z-index', '0');
        nContainer.html("");
    });
}

function raiseNotification(message, time)
{
    startNotification(message, 'primary', 'secondary', time);
}

function raiseError(message, time)
{
    startNotification(message, 'error', 'white-bg', time);
}

// NOTIFICATIONS - SERVER COMM
socket.on('error', message => {
    raiseError(message, LONG);
});

socket.on('notification', message => {
    raiseNotification(message, LONG);
});
$(document).ready(function(){
	// Compute how big everything should be.
	var useheight = $(window).height() - 42;
	$('.ingame').height(useheight).prop({scrollTop: $('.ingame').prop('scrollHeight')});
	$('#post-chat').height(useheight).prop({scrollTop: $('#post-chat').prop('scrollHeight')});
});


jQuery(function(){
    

			function openprompt(){

//'How did you first find out about this site?<div class="field"><select name="rate_find" id="rate_find"><option value="Search">Search</option><option value="Online Publication">Online Publication</option><option value="friend">A Friend</option><option value="No Clue">No Clue</option></select></div>',
						
				var temp = {
					state0: {
						html:'<p >Submit your question or request for a free consultation.</p><div class="field" id="impromptu_dialog"><textarea id="question" name="question"></textarea><br/>My Email Address <input id="email" placeholder="include your e-mail so we can provide a quick response..." type="text"/></div>',
						buttons: { Cancel: false, Submit: true },
						focus: 1,
						submit:function(v,m,f){ 
							if(!v)
								return $.prompt.close();
							
							var question_val = $('#impromptu_dialog').find('#question').val();
							var email_val = $('#impromptu_dialog').find('#email').val();

							if (!email_val) return alert('Please include your email address so we can provide a quick response');
							
                            $.ajax({
                                url: "/admin/question",
                                type: "POST",
                                data: {
                                    "email": email_val,
                                    "question": question_val
                                    },
                                success: function(msg){
                                    }
                            });

							$.prompt.close();
						}
					}
				}
				
				$.prompt(temp,{
					callback: function(v,m,f){
					}
				});
			}
			
			$('.contact_us').click(openprompt);
			
			
});
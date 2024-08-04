$(document).ready(function() {
    $('#testType').change(function() {
        if ($(this).val() === 'channel') {
            $('#channelControl').show();
            $('#effectControl').hide();
        } else if ($(this).val() === 'effect') {
            $('#channelControl').hide();
            $('#effectControl').show();
        }
    });

    $('#startTest').click(function() {
        var selectedRooms = [];
        $('input[name="room"]:checked').each(function() {
            selectedRooms.push($(this).val());
        });

        if (selectedRooms.length === 0) {
            alert('Please select at least one room.');
            return;
        }

        var testType = $('#testType').val();
        var testData = {
            testType: testType,
            rooms: selectedRooms
        };

        if (testType === 'channel') {
            testData.channelValues = {
                total_dimming: $('#total_dimming').val(),
                r_dimming: $('#r_dimming').val(),
                g_dimming: $('#g_dimming').val(),
                b_dimming: $('#b_dimming').val(),
                w_dimming: $('#w_dimming').val(),
                total_strobe: $('#total_strobe').val()
            };
        } else if (testType === 'effect') {
            testData.effectName = $('#effectSelect').val();
            if (!testData.effectName) {
                alert('Please select an effect.');
                return;
            }
        }

        $.ajax({
            url: '/run_test',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(testData),
            success: function(response) {
                $('#testResults').html('<p>' + response.message + '</p>');
            },
            error: function(xhr, status, error) {
                $('#testResults').html('<p>Error: ' + xhr.responseJSON.error + '</p>');
            }
        });
    });

    $('#stopTest').click(function() {
        $.ajax({
            url: '/stop_test',
            type: 'POST',
            success: function(response) {
                $('#testResults').html('<p>' + response.message + '</p>');
            },
            error: function(xhr, status, error) {
                $('#testResults').html('<p>Error: ' + xhr.responseJSON.error + '</p>');
            }
        });
    });

    // Update value displays for channel controls
    $('#channelControl input[type="range"]').on('input', function() {
        $('#' + $(this).attr('id') + '_value').text($(this).val());
    });

    // Continuous update of channel values
    setInterval(function() {
        if ($('#testType').val() === 'channel') {
            $('#startTest').click();
        }
    }, 100); // Update every 100ms
});

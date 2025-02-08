function CertificatesXBlock(runtime, element) {
    function generateCertificate(event) {
        const button = event.target;
        const certificateType = $(button).data('certificate-type');
        const handlerUrl = runtime.handlerUrl(element, 'generate_certificate');

        $.post(handlerUrl, JSON.stringify({ certificate_type: certificateType }))
          .done(function(data) {
              const messageArea = $(element).find('#message-area-' + certificateType);
              if (data.status === 'success') {
                  messageArea.html('<p style="color:green;">Certificate generation initiated successfully.</p>');
              } else {
                  messageArea.html('<p style="color:red;">' + data.message + '</p>');
              }
          })
          .fail(function() {
              const messageArea = $(element).find('#message-area-' + certificateType);
              messageArea.html('<p style="color:red;">An error occurred while processing your request.</p>');
          });
    }

    $(element).find('.generate-certificate').on('click', generateCertificate);
}

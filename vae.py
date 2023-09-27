from typing import Tuple
import torch
 
class StandardVAE(torch.nn.Module):
    def __init__(self,
                 n_latent: int,
                 beta: float,
                 encoder,
                 decoder,
                 batch: int = 1) -> None:
        super(StandardVAE, self).__init__()
        # Initializing the class variables
        self.n_latent = n_latent
        self.beta = beta
        self.batch = batch

        self.encoder = encoder
        self.decoder = decoder
        self.hidden_units = self.encoder.output_size()

        # Early Stopping
        self.patience = 10
        self.delta = 1e-4
        self.best_score = None
        self.num_bad_epochs = 0

        # Dense Encoder Bottleneck
        self.enc_dense1 = torch.nn.Linear(self.hidden_units, 2048)
        self.enc_dense1_af = torch.nn.LeakyReLU(0.1)

        self.enc_dense2 = torch.nn.Linear(2048, 1000)
        self.enc_dense2_af = torch.nn.LeakyReLU(0.1)

        self.enc_dense3 = torch.nn.Linear(1000, 250)
        self.enc_dense3_af = torch.nn.LeakyReLU(0.1)

        # Latent Variables Calculation
        self.enc_dense4_mu = torch.nn.Linear(250, self.n_latent)
        self.enc_dense4_mu_af = torch.nn.LeakyReLU(0.1)

        self.enc_dense4_var = torch.nn.Linear(250, self.n_latent)
        self.enc_dense4_var_af = torch.nn.LeakyReLU(0.1)

        # Dense Decoder Bottleneck
        self.dec_dense4 = torch.nn.Linear(self.n_latent, 250)
        self.dec_dense4_af = torch.nn.LeakyReLU(0.1)

        self.dec_dense3 = torch.nn.Linear(250, 1000)
        self.dec_dense3_af = torch.nn.LeakyReLU(0.1)

        self.dec_dense2 = torch.nn.Linear(1000, 2048)
        self.dec_dense2_af = torch.nn.LeakyReLU(0.1)

        self.dec_dense1 = torch.nn.Linear(2048, self.hidden_units)
        self.dec_dense1_af = torch.nn.LeakyReLU(0.1)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        # Convolutional Encoder Network
        z = self.encoder.forward(x)

        # Dense Encoder Bottleneck
        z = z.view(z.size(0), -1) # Converting a 4D tensor (output of convolutional layer) to 1D tensor
        z = self.enc_dense1(z)
        z = self.enc_dense1_af(z)

        z = self.enc_dense2(z)
        z = self.enc_dense2_af(z)

        z = self.enc_dense3(z)
        z = self.enc_dense3_af(z)

        mu = self.enc_dense4_mu(z)
        mu = self.enc_dense4_mu_af(mu)

        var = self.enc_dense4_var(z)
        var = self.enc_dense4_var_af(var)

        return (mu, var)
    
    def decode(self, z: torch.Tensor) -> torch.Tensor:
        # Dense Decoder Bottleneck
        y = self.dec_dense4(z)
        y = self.dec_dense4_af(y)

        y = self.dec_dense3(y)
        y = self.dec_dense3_af(y)

        y = self.dec_dense2(y)
        y = self.dec_dense2_af(y)

        y = self.dec_dense1(y)
        y = self.dec_dense1_af(y)

        # Convolutional Decoder Network
        y = self.decoder.forward(y)

        return y
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor]:
        mu, logvar = self.encode(x)
        std = torch.exp(logvar / 2)
        eps = torch.randn_like(std)
        z = mu + std * eps
        out = self.decode(z)
        return out, mu, logvar
    
    def testing(self,
                data_path: str,
                weight_file: str):
        # Using cuda if available
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print (f'Using device: {device}')
        network = self.to(device)
        network.load_state_dict(torch.load(weight_file)) # Load weights from the .pt file
        network.eval() # Set the network in evalution mode

        dataset = self.encoder.preprocess(data_path)

        # Set up a Python iterable over the input test dataset
        test_loader = torch.utils.data.DataLoader(
            dataset=dataset,
            batch_size=self.batch,
            shuffle=True,
            drop_last=True)

        final_input = []
        final_class = []
        final_output = []
        final_mean = []
        final_var = []
        for data in test_loader:
            input, class_name = data
            final_input.append(input)
            final_class.append(int(class_name))
            input = input.to(device)
            with torch.no_grad():
                output, mean, logvariance = network.forward(input)
                final_mean.append(mean)
                final_var.append(torch.exp(logvariance/2))
                final_output.append(output)

        result = dict()
        result['final_input'] = final_input
        result['final_class'] = final_class
        result['final_output'] = final_output
        result['final_mean'] = final_mean
        result['final_var'] = final_var
        return result
    
    def check(self, curr_score, model, weights_file) :
        if self.best_score==None:
            self.best_score = curr_score
            state_dict = model.state_dict()
            torch.save(state_dict, weights_file)
        else:
            if self.best_score-curr_score>self.delta:
                self.best_score = curr_score
                self.num_bad_epochs = 0
                state_dict = model.state_dict()
                torch.save(state_dict, weights_file)
            else:
                self.num_bad_epochs += 1
        if self.num_bad_epochs==self.patience:
            return True
        else:
            return False
        
    def train_self(self,
                    data_path: str,
                    val_path: str,
                    epochs: int,
                    learning_rate: float,
                    weights_file: str,
                    hyperparameters_file: str) -> None:
        # Using cuda (GPU) if available
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print (f'Using device: {device}')

        # Set the network in training mode
        network = self.to(device)
        network.train()

        dataset = self.encoder.preprocess(data_path)
        val_dataset = self.encoder.preprocess(val_path)

        # Sets up a Python iterable over the input training dataset
        train_loader = torch.utils.data.DataLoader(
            dataset=dataset,
            batch_size=self.batch,
            shuffle=True,
            drop_last=True)
        
        # Sets up a Python iterable over the input validation dataset
        val_loader = torch.utils.data.DataLoader(
            dataset=val_dataset,
            batch_size=self.batch,
            shuffle=True,
            drop_last=True)

        # Save the hyperparameters used for training the VAE Network
        hyperparameters = {}
        hyperparameters["n_latent"] = self.n_latent
        hyperparameters["beta"] = self.beta
        torch.save(hyperparameters, hyperparameters_file)

        # Using Adam Optimizer for training
        optimizer = torch.optim.Adam(network.parameters(), lr=learning_rate)

        for epoch in range(epochs):
            epoch_loss = 0
            for data in train_loader:
                input, class_name = data
                input = input.to(device)

                # Passing the input image through VAE Network
                out, mu, logvar = network.forward(input)

                # KL-Divergence Loss (Regularization loss in VAE Loss function)
                kl_loss = torch.mul(input=torch.sum(mu.pow(2) + logvar.exp() - logvar - 1), other=0.5)

                # Mean Square Error Loss (Reconstruction loss in VAE Loss function)
                mse_loss = torch.nn.functional.mse_loss(out, input)

                # Total Loss = Regularization Loss + Beta * Reconstruction Loss
                loss = kl_loss + torch.mul(mse_loss, self.beta)

                optimizer.zero_grad() # Sets gradients of all model parameters to zero
                loss.backward() # Perform Back-Propogation
                optimizer.step() # Performs a single optimization step (parameter update)
                epoch_loss += loss

            val_loss = 0
            for data in val_loader:
                input, class_name = data
                input = input.to(device)
                output, mu, logvar = network.forward(input)
                mse_val_loss = torch.nn.functional.mse_loss(output, input)
                val_loss += mse_val_loss
            if self.check(val_loss, network, weights_file):
                print(f'Early Stopping at epoch {epoch}')
                break
            print(f'Epoch: {epoch}; Training Loss: {epoch_loss}; Validation Loss: {val_loss}')
        print('Training finished, saving weights...')
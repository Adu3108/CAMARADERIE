import torch
import torchvision
import matplotlib.pyplot as plt
from PIL import Image
import os

from DCSAE.DC_SAE import DCSAE
from DCSAE.NumDC_SAE import NumDCSAE

class DCSAE_Trainer:
    def __init__(self, n_latent, alpha, beta, gamma, rho, n_chan, input_d, train_path, val_path, weights_path, hyperparameters_path):
        super(DCSAE_Trainer, self).__init__()
        self.n_latent = n_latent
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.rho = rho
        self.input_d = input_d
        self.n_chan = n_chan
        self.num_epochs = 100
        self.lr = 1e-4

        self.dataset = train_path
        self.validation_dataset = val_path
        self.weights_path = weights_path
        self.hyperparameters_path = hyperparameters_path

        # Creating an instance of VAE Network for training at Client A
        self.ClientA_Network = DCSAE(
            self.n_latent,
            self.alpha,
            self.beta,
            self.gamma,
            self.rho,
            self.n_chan,
            self.input_d
        )
        
    def train(self):
        print(f'alpha={self.alpha}')
        print(f'beta={self.beta}')
        print(f'gamma={self.gamma}')
        print(f'rho={self.rho}')
        print(f'n_latent={self.n_latent}')
        print(f'Using data set {self.dataset}')

        # Training the created VAE instance on the labelled dataset at Client A
        self.ClientA_Network.train_self(
            data_path=self.dataset,
            val_path=self.validation_dataset,
            epochs=self.num_epochs,
            learning_rate = self.lr,
            weights_file=self.weights_path,
            hyperparameters_file = self.hyperparameters_path)

    def latent(self):
        result = self.ClientA_Network.testing(data_path=self.dataset, weight_file=self.weights_path)

        ClientA_class = result["final_class"]

        # Extracting latent space representation of each image in the training dataset
        ClientA_Z = []
        for i in range(len(result["final_negative_mean"])):
            eps = torch.randn_like(result["final_negative_var"][i])
            mean_cpu = result["final_negative_mean"][i].cpu().detach().numpy()
            variance_cpu = result["final_negative_var"][i].cpu().detach().numpy()
            eps = eps.cpu().detach().numpy()
            z = mean_cpu + variance_cpu * eps
            ClientA_Z.append(z)

        return ClientA_Z, ClientA_class

    def visualize(self, ClientA_Z, ClientA_class):
        colors = ['red','green']
        for i in range(len(ClientA_Z)):
            z = ClientA_Z[i]
            plt.scatter(z[0][0], z[0][1], c=colors[ClientA_class[i]])
        plt.savefig("./latent.png", format="png")
    
    def reconstruct(self):
        # Generate a white image
        white_array = torch.ones((3, 224, 2))
        white_array.to(torch.int32)
        device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        white_array = white_array.to(device)

        # Get the reconstructions
        result = self.ClientA_Network.testing(data_path=self.dataset, weight_file=self.weights_path)

        # Create a directory to store the reconstructions
        os.mkdir("./Reconstruction")

        for i in range(len(result["final_input"]))[:10]:
            # Squeeze the image tensor to 3 dimensions (channels x height x width)
            # In case of GrayScale Images, repeat the same tensor in the 3 channels
            input_image_tensor = torch.squeeze(result["final_input"][i])
            if input_image_tensor.shape[0] != 3:
                input_image_tensor = input_image_tensor.repeat(3, 1, 1)
            reconstruction_image_tensor = torch.squeeze(result["final_output"][i])
            if reconstruction_image_tensor.shape[0] != 3:
                reconstruction_image_tensor = reconstruction_image_tensor.repeat(3, 1, 1)

            input_image_tensor = input_image_tensor.to(device)
            reconstruction_image_tensor = reconstruction_image_tensor.to(device)

            # Concatenate the input image and the reconstructed image
            concatenate_image = torch.cat([input_image_tensor, white_array, reconstruction_image_tensor], 2)
            image = torchvision.transforms.ToPILImage()(concatenate_image)
            image = image.resize((384,128), Image.LANCZOS)
            image.save(f'./Reconstruction/reconstruction_{i}.jpg')

class NumDCSAE_Trainer:
    def __init__(self, n_latent, alpha, beta, gamma, rho, train_data, val_data, train_labels, val_labels, weights_path, hyperparameters_path):
        super(NumDCSAE_Trainer, self).__init__()
        self.n_latent = n_latent
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.rho = rho
        self.num_epochs = 100
        self.lr = 1e-4

        self.dataset = train_data
        self.validation_dataset = val_data
        self.train_labels = train_labels
        self.val_labels = val_labels
        self.weights_path = weights_path
        self.hyperparameters_path = hyperparameters_path

        # Creating an instance of VAE Network for training at Client A
        self.ClientA_Network = NumDCSAE(
            self.n_latent,
            self.alpha,
            self.beta,
            self.gamma,
            self.rho,
            self.dataset.shape[1]
        )
        
    def train(self):
        print(f'alpha={self.alpha}')
        print(f'beta={self.beta}')
        print(f'gamma={self.gamma}')
        print(f'rho={self.rho}')
        print(f'n_latent={self.n_latent}')

        # Training the created VAE instance on the labelled dataset at Client A
        self.ClientA_Network.train_self(
            train_data=self.dataset,
            val_data=self.validation_dataset,
            train_labels=self.train_labels,
            val_labels=self.val_labels,
            epochs=self.num_epochs,
            learning_rate = self.lr,
            weights_file=self.weights_path,
            hyperparameters_file = self.hyperparameters_path)

    def latent(self):
        result = self.ClientA_Network.testing(test_data=self.dataset, labels=self.train_labels, weight_file=self.weights_path)

        ClientA_class = result["final_class"]

        # Extracting latent space representation of each image in the training dataset
        ClientA_Z = []
        for i in range(len(result["final_negative_mean"])):
            eps = torch.randn_like(result["final_negative_var"][i])
            mean_cpu = result["final_negative_mean"][i].cpu().detach().numpy()
            variance_cpu = result["final_negative_var"][i].cpu().detach().numpy()
            eps = eps.cpu().detach().numpy()
            z = mean_cpu + variance_cpu * eps
            ClientA_Z.append(z)

        return ClientA_Z, ClientA_class

    def visualize(self, ClientA_Z, ClientA_class):
        colors = ['red','green']
        for i in range(len(ClientA_Z)):
            z = ClientA_Z[i]
            plt.scatter(z[0], z[1], c=colors[ClientA_class[i]])
        plt.savefig("./latent.png", format="png")